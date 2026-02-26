"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { formatDate, formatPercent, joinChannels } from "./format";

const OFFICIAL_SIDO_OFFICES = ["광역자치단체장", "광역의회", "교육감"];

function getLonLatPoints(feature) {
  if (feature.geometry.type === "Polygon") {
    return feature.geometry.coordinates.flat();
  }
  return feature.geometry.coordinates.flat(2);
}

function projectFeature(feature, projectFn) {
  if (feature.geometry.type === "Polygon") {
    return feature.geometry.coordinates.map((ring) => ring.map((point) => projectFn(point)));
  }
  return feature.geometry.coordinates.flatMap((polygon) => polygon.map((ring) => ring.map((point) => projectFn(point))));
}

function toPath(rings) {
  return rings
    .map((ring) => {
      if (!ring.length) return "";
      const [first, ...rest] = ring;
      const commands = [`M ${first.x.toFixed(2)} ${first.y.toFixed(2)}`];
      for (const point of rest) commands.push(`L ${point.x.toFixed(2)} ${point.y.toFixed(2)}`);
      commands.push("Z");
      return commands.join(" ");
    })
    .join(" ");
}

function averageCenter(rings) {
  const points = rings.flat();
  if (!points.length) return { x: 0, y: 0 };
  return points.reduce(
    (acc, point) => ({ x: acc.x + point.x / points.length, y: acc.y + point.y / points.length }),
    { x: 0, y: 0 }
  );
}

function pickLatestByRegion(items) {
  const map = new Map();
  for (const item of items || []) {
    const candidates = new Set();
    const rawRegionCode = typeof item?.region_code === "string" ? item.region_code.trim() : "";
    const rawAudienceCode = typeof item?.audience_region_code === "string" ? item.audience_region_code.trim() : "";
    if (rawRegionCode) {
      candidates.add(rawRegionCode);
      if (/^\d{2}-\d{3}$/.test(rawRegionCode)) candidates.add(`${rawRegionCode.slice(0, 2)}-000`);
    }
    if (rawAudienceCode) {
      candidates.add(rawAudienceCode);
      if (/^\d{2}-\d{3}$/.test(rawAudienceCode)) candidates.add(`${rawAudienceCode.slice(0, 2)}-000`);
    }
    for (const code of candidates) {
      const existing = map.get(code);
      if (!existing) {
        map.set(code, item);
        continue;
      }
      const existingDate = existing.survey_end_date || "";
      const nextDate = item.survey_end_date || "";
      if (nextDate >= existingDate) map.set(code, item);
    }
  }
  return map;
}

function normalizeOfficeType(value) {
  return typeof value === "string" ? value.trim() : "";
}

function toSortableDate(value) {
  if (typeof value !== "string" || !value.trim()) return "";
  return value.trim();
}

function electionPriority(row) {
  const source = typeof row?.source === "string" ? row.source.trim().toLowerCase() : "";
  let score = 0;
  if ((row?.topology || "official") === "official") score += 100;
  if (source === "master" || source === "code_master") score += 50;
  if (!row?.is_fallback) score += 20;
  if (!row?.is_placeholder) score += 12;
  if (row?.has_poll_data) score += 8;
  if (row?.has_candidate_data) score += 4;
  if (row?.is_active) score += 2;
  return score;
}

function pickRepresentativeElection(prev, next) {
  if (!prev) return next;
  const prevPriority = electionPriority(prev);
  const nextPriority = electionPriority(next);
  if (nextPriority !== prevPriority) return nextPriority > prevPriority ? next : prev;

  const prevDate = toSortableDate(prev.latest_survey_end_date);
  const nextDate = toSortableDate(next.latest_survey_end_date);
  if (nextDate !== prevDate) return nextDate > prevDate ? next : prev;

  const prevMatchup = typeof prev.matchup_id === "string" ? prev.matchup_id : "";
  const nextMatchup = typeof next.matchup_id === "string" ? next.matchup_id : "";
  return nextMatchup > prevMatchup ? next : prev;
}

function normalizeElectionStatus(row) {
  if (typeof row?.status === "string" && row.status.trim()) return row.status.trim();
  return row?.has_poll_data ? "데이터 준비 완료" : "조사 데이터 없음";
}

function fallbackElectionTitle(regionName, officeType) {
  const normalizedRegion = typeof regionName === "string" ? regionName.trim() : "";
  if (normalizedRegion.includes("세종")) {
    if (officeType === "광역자치단체장") return "세종시장";
    if (officeType === "광역의회") return "세종시의회";
    if (officeType === "교육감") return "세종교육감";
  }
  if (!normalizedRegion) return officeType;
  return `${normalizedRegion} ${officeType}`;
}

function formatSurveyMeta(value) {
  return formatDate(value);
}

function formatSampleMeta(value) {
  if (value === null || value === undefined || value === "") return "표본 정보 없음";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "표본 정보 없음";
  return `표본 ${numeric.toLocaleString("ko-KR")}명`;
}

function formatMarginMeta(value) {
  if (value === null || value === undefined || value === "") return "오차 정보 없음";
  const numeric = Number(value);
  if (Number.isFinite(numeric)) return `오차 ±${numeric}%p`;
  return `오차 ${String(value)}`;
}

function buildOfficialSlots(elections, { regionCode, regionName }) {
  const byOffice = new Map();
  for (const raw of elections || []) {
    const officeType = normalizeOfficeType(raw?.office_type);
    if (!officeType || !OFFICIAL_SIDO_OFFICES.includes(officeType)) continue;

    const normalized = {
      ...raw,
      office_type: officeType,
      status: normalizeElectionStatus(raw)
    };
    byOffice.set(officeType, pickRepresentativeElection(byOffice.get(officeType), normalized));
  }

  return OFFICIAL_SIDO_OFFICES.map((officeType) => {
    const picked = byOffice.get(officeType);
    if (picked) return picked;
    return {
      matchup_id: `placeholder|${officeType}|${regionCode}`,
      region_code: regionCode,
      office_type: officeType,
      title: fallbackElectionTitle(regionName, officeType),
      is_active: true,
      topology: "official",
      topology_version_id: null,
      is_placeholder: true,
      is_fallback: true,
      source: "generated",
      has_poll_data: false,
      has_candidate_data: false,
      latest_survey_end_date: null,
      latest_matchup_id: null,
      status: "조사 데이터 없음"
    };
  });
}

export default function RegionalMapPanel({
  items,
  apiBase,
  initialSelectedRegionCode = null,
  selectedRegionHint = ""
}) {
  const [hoveredCode, setHoveredCode] = useState(null);
  const [focusedCode, setFocusedCode] = useState(null);
  const [selectedCode, setSelectedCode] = useState(initialSelectedRegionCode);
  const [geoState, setGeoState] = useState("loading");
  const [geoJson, setGeoJson] = useState(null);
  const [electionsState, setElectionsState] = useState("idle");
  const [elections, setElections] = useState([]);

  useEffect(() => {
    setSelectedCode(initialSelectedRegionCode || null);
  }, [initialSelectedRegionCode]);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setGeoState("loading");
      try {
        const res = await fetch("/geo/kr_adm1_simplified.geojson", { cache: "no-store" });
        if (!res.ok) throw new Error("geo fetch failed");
        const data = await res.json();
        if (!mounted) return;
        setGeoJson(data);
        setGeoState("ready");
      } catch {
        if (!mounted) return;
        setGeoState("error");
      }
    };
    void load();
    return () => {
      mounted = false;
    };
  }, []);

  const latestByRegion = useMemo(() => pickLatestByRegion(items), [items]);

  const features = useMemo(() => geoJson?.features || [], [geoJson]);

  const projected = useMemo(() => {
    if (!features.length) return new Map();
    const allPoints = features.flatMap((feature) => getLonLatPoints(feature));
    const lons = allPoints.map((pt) => pt[0]);
    const lats = allPoints.map((pt) => pt[1]);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);

    const width = 760;
    const height = 900;
    const padding = 30;

    const projectPoint = ([lon, lat]) => {
      const lonRange = Math.max(maxLon - minLon, 0.1);
      const latRange = Math.max(maxLat - minLat, 0.1);
      const x = padding + ((lon - minLon) / lonRange) * (width - padding * 2);
      const y = padding + ((maxLat - lat) / latRange) * (height - padding * 2);
      return { x, y };
    };

    return new Map(
      features.map((feature) => {
        const rings = projectFeature(feature, projectPoint);
        return [feature.properties.region_code, { path: toPath(rings), center: averageCenter(rings) }];
      })
    );
  }, [features]);

  const activeCode = selectedCode || focusedCode || hoveredCode;
  const activeFeature = features.find((feature) => feature.properties.region_code === activeCode) || null;
  const activeLatest = activeCode ? latestByRegion.get(activeCode) || null : null;
  const modeLabel = selectedCode ? "선택 고정" : focusedCode ? "키보드 포커스" : hoveredCode ? "hover 미리보기" : "대기";

  useEffect(() => {
    if (!selectedCode) {
      setElections([]);
      setElectionsState("idle");
      return;
    }
    let cancelled = false;
    const loadElections = async () => {
      setElectionsState("loading");
      try {
        const params = new URLSearchParams({ topology: "official" });
        const res = await fetch(`${apiBase}/api/v1/regions/${encodeURIComponent(selectedCode)}/elections?${params.toString()}`, {
          cache: "no-store"
        });
        if (!res.ok) throw new Error("elections fetch failed");
        const body = await res.json();
        if (cancelled) return;
        setElections(Array.isArray(body) ? body : []);
        setElectionsState("ready");
      } catch {
        if (cancelled) return;
        setElections([]);
        setElectionsState("error");
      }
    };
    void loadElections();
    return () => {
      cancelled = true;
    };
  }, [apiBase, selectedCode]);

  const selectedFeature =
    (selectedCode && features.find((feature) => feature.properties.region_code === selectedCode)) || null;
  const visibleElections = useMemo(() => {
    if (!selectedCode) return [];
    const regionName = selectedFeature?.properties?.region_name || "";
    return buildOfficialSlots(elections, { regionCode: selectedCode, regionName });
  }, [elections, selectedCode, selectedFeature]);

  return (
    <section className="panel region-layout">
      <div className="map-shell">
        {geoState === "loading" ? <div className="empty-state">지도를 불러오는 중...</div> : null}
        {geoState === "error" ? <div className="empty-state">지도를 불러오지 못했습니다.</div> : null}
        {geoState === "ready" ? (
          <svg viewBox="0 0 760 900" role="img" aria-label="대한민국 광역 지도" className="korea-map">
            {features.map((feature) => {
              const regionCode = feature.properties.region_code;
              const projectedFeature = projected.get(regionCode);
              if (!projectedFeature) return null;

              const hasData = latestByRegion.has(regionCode);
              const isActive = activeCode === regionCode;

              return (
                <g
                  key={regionCode}
                  className={`map-region ${focusedCode === regionCode ? "is-focused" : ""}`}
                  role="button"
                  tabIndex={0}
                  aria-label={`${feature.properties.region_name || regionCode}, ${hasData ? "최신 조사 있음" : "최신 조사 없음"}`}
                  onMouseEnter={() => setHoveredCode(regionCode)}
                  onMouseLeave={() => setHoveredCode((prev) => (prev === regionCode ? null : prev))}
                  onFocus={() => setFocusedCode(regionCode)}
                  onBlur={() => setFocusedCode((prev) => (prev === regionCode ? null : prev))}
                  onClick={() => setSelectedCode((prev) => (prev === regionCode ? null : regionCode))}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedCode((prev) => (prev === regionCode ? null : regionCode));
                    }
                  }}
                >
                  <path
                    d={projectedFeature.path}
                    fill={isActive ? "#22d3ee" : hasData ? "#cffafe" : "#dbe4ee"}
                    stroke={isActive ? "#0f172a" : "#55657a"}
                    strokeWidth={isActive ? 2.6 : 1.4}
                  />
                </g>
              );
            })}
          </svg>
        ) : null}
      </div>

      <aside className="region-detail" aria-live="polite">
        <header>
          <h3>지역 인터랙션</h3>
          <p>지도에서 지역을 선택하면 최신 조사와 연결된 매치업을 확인할 수 있습니다.</p>
        </header>

        {selectedRegionHint ? (
          <div className="param-callout">
            baseline selected_region 적용: <strong>{selectedRegionHint}</strong>
          </div>
        ) : null}

        {!activeCode ? <div className="empty-state">지역을 선택해 주세요.</div> : null}

        {activeCode ? (
          <div className="region-block">
            <p className="region-name">{activeFeature?.properties?.region_name || activeCode}</p>
            <p className="region-code">{activeCode}</p>
            <div className="badge-row">
              <span className={`state-badge ${activeLatest ? "ok" : "info"}`}>{modeLabel}</span>
              <span className={`state-badge ${activeLatest ? "ok" : "warn"}`}>{activeLatest ? "최신 조사 있음" : "최신 조사 없음"}</span>
            </div>
          </div>
        ) : null}

        {activeLatest ? (
          <div className="region-block">
            <strong>{activeLatest.title}</strong>
            <p>대표값: {formatPercent(activeLatest.value_mid)}</p>
            <p className="muted-text">최신 조사일: {formatSurveyMeta(activeLatest.survey_end_date)}</p>
            <p className="muted-text">조사기관: {activeLatest.pollster || "조사기관 미확인"}</p>
            <p className="muted-text">{formatSampleMeta(activeLatest.sample_size)}</p>
            <p className="muted-text">{formatMarginMeta(activeLatest.margin_of_error || activeLatest.moe)}</p>
            <p className="muted-text">채널: {joinChannels(activeLatest.source_channels)}</p>
          </div>
        ) : null}

        {activeCode && !activeLatest ? (
          <div className="region-block">
            <strong>최신 조사 메타</strong>
            <p className="muted-text">최신 조사일: -</p>
            <p className="muted-text">조사기관: 조사 데이터 없음</p>
            <p className="muted-text">표본 정보: 없음</p>
            <p className="muted-text">오차 정보: 없음</p>
            <p className="muted-text">안내: 이 지역은 최신 조사 데이터가 없어 placeholder 메타를 표시합니다.</p>
          </div>
        ) : null}

        {selectedCode ? (
          <div className="region-block">
            <strong>연결 선거</strong>
            {electionsState === "loading" ? <p className="muted-text">불러오는 중...</p> : null}
            {electionsState === "error" ? <p className="muted-text">선거 목록을 불러오지 못했습니다.</p> : null}
            {electionsState === "ready" && visibleElections.length === 0 ? <p className="muted-text">연결된 선거가 없습니다.</p> : null}
            {electionsState === "ready" && visibleElections.length > 0 ? (
              <ul className="election-list">
                {visibleElections.map((election) => {
                  const navigationMatchupId =
                    election.latest_matchup_id || (election.is_placeholder ? "" : election.matchup_id || "");
                  const canNavigate = Boolean(navigationMatchupId);
                  const statusText = normalizeElectionStatus(election);
                  const key = `${election.office_type}:${election.matchup_id || election.region_code || "unknown"}`;

                  return (
                    <li key={key}>
                      {canNavigate ? (
                        <Link href={`/matchups/${encodeURIComponent(navigationMatchupId)}`}>
                          <span>{election.office_type}</span>
                          <strong>{election.title}</strong>
                          <span>{statusText}</span>
                        </Link>
                      ) : (
                        <div>
                          <span>{election.office_type}</span>
                          <strong>{election.title}</strong>
                          <span>{statusText}</span>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </div>
        ) : null}
      </aside>
    </section>
  );
}
