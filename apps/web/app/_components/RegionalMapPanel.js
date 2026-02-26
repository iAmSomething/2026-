"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { formatDate, formatPercent, joinChannels } from "./format";

const REGION_PREFIX_LABELS = {
  "11": "서울특별시",
  "21": "부산광역시",
  "22": "대구광역시",
  "23": "인천광역시",
  "24": "광주광역시",
  "25": "대전광역시",
  "26": "울산광역시",
  "29": "세종특별자치시",
  "31": "경기도",
  "32": "강원특별자치도",
  "33": "충청북도",
  "34": "충청남도",
  "35": "전북특별자치도",
  "36": "전라남도",
  "37": "경상북도",
  "38": "경상남도",
  "39": "제주특별자치도"
};

const REGION_SHORT_LABELS = {
  "KR-11": "서울",
  "KR-21": "부산",
  "KR-22": "대구",
  "KR-23": "인천",
  "KR-24": "광주",
  "KR-25": "대전",
  "KR-26": "울산",
  "KR-29": "세종",
  "KR-31": "경기",
  "KR-32": "강원",
  "KR-33": "충북",
  "KR-34": "충남",
  "KR-35": "전북",
  "KR-36": "전남",
  "KR-37": "경북",
  "KR-38": "경남",
  "KR-39": "제주"
};

const DENSE_LABEL_CODES = new Set(["KR-11", "KR-22", "KR-23", "KR-26", "KR-31", "KR-38"]);

const LABEL_OFFSETS = {
  "KR-11": { x: -22, y: -10 },
  "KR-23": { x: -35, y: 12 },
  "KR-31": { x: 12, y: 0 },
  "KR-22": { x: 18, y: 4 },
  "KR-26": { x: 24, y: 10 },
  "KR-38": { x: 22, y: 16 },
  "KR-29": { x: -8, y: 12 }
};

const SLOT_ORDER = ["metro_mayor", "metro_council", "superintendent"];

const SLOT_LABELS = {
  metro_mayor: "광역자치단체장",
  metro_council: "광역의회",
  superintendent: "교육감"
};

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

function regionPrefix(value) {
  if (!value) return null;
  const match = String(value).trim().match(/(?:KR-)?(\d{2})/i);
  return match ? match[1] : null;
}

function toMapRegionCode(value) {
  const prefix = regionPrefix(value);
  return prefix ? `KR-${prefix}` : null;
}

function toApiRegionCode(value) {
  const prefix = regionPrefix(value);
  return prefix ? `${prefix}-000` : null;
}

function normalizeOfficeType(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (["metro_mayor", "광역자치단체장", "시도지사", "도지사"].includes(normalized)) return "metro_mayor";
  if (["metro_council", "광역의회", "시도의회"].includes(normalized)) return "metro_council";
  if (["superintendent", "교육감"].includes(normalized)) return "superintendent";
  return null;
}

function toDateValue(value) {
  if (!value) return 0;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function chooseRepresentative(elections) {
  const sorted = [...elections].sort((a, b) => {
    const aHasData = a.has_poll_data ? 1 : 0;
    const bHasData = b.has_poll_data ? 1 : 0;
    if (aHasData !== bHasData) return bHasData - aHasData;
    return toDateValue(b.latest_survey_end_date) - toDateValue(a.latest_survey_end_date);
  });
  return sorted[0] || null;
}

function buildSlotTitle({ slotKey, regionName, regionCode, election }) {
  if (election?.title) return election.title;
  const prefix = regionPrefix(regionCode);
  if (prefix === "29") {
    if (slotKey === "metro_mayor") return "세종시장";
    if (slotKey === "metro_council") return "세종시의회";
    if (slotKey === "superintendent") return "세종교육감";
  }
  const base = regionName || (prefix ? REGION_PREFIX_LABELS[prefix] : null) || regionCode || "선택 지역";
  if (slotKey === "metro_mayor") return `${base} 광역자치단체장`;
  if (slotKey === "metro_council") return `${base} 광역의회`;
  return `${base} 교육감`;
}

function slotStatus({ electionsState, election }) {
  if (electionsState === "loading") return { tone: "info", text: "불러오는 중" };
  if (electionsState === "error") return { tone: "warn", text: "조회 실패" };
  if (election?.has_poll_data) return { tone: "ok", text: "조사 데이터 있음" };
  return { tone: "warn", text: "조사 데이터 없음" };
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

function freshnessBadge(hours) {
  const numeric = Number(hours);
  if (!Number.isFinite(numeric)) return { tone: "info", text: "신선도 -" };
  if (numeric <= 48) return { tone: "ok", text: `신선도 ${numeric.toFixed(1)}h` };
  if (numeric <= 96) return { tone: "info", text: `신선도 ${numeric.toFixed(1)}h` };
  return { tone: "warn", text: `신선도 ${numeric.toFixed(1)}h` };
}

function sampleBadge(sampleSize) {
  const numeric = Number(sampleSize);
  if (!Number.isFinite(numeric) || numeric <= 0) return { tone: "info", text: "표본 미확인" };
  return { tone: "info", text: `표본 ${numeric.toLocaleString("ko-KR")}명` };
}

export default function RegionalMapPanel({
  items,
  apiBase,
  initialSelectedRegionCode = null,
  selectedRegionHint = ""
}) {
  const [hoveredCode, setHoveredCode] = useState(null);
  const [focusedCode, setFocusedCode] = useState(null);
  const [selectedCode, setSelectedCode] = useState(toMapRegionCode(initialSelectedRegionCode));
  const [geoState, setGeoState] = useState("loading");
  const [geoJson, setGeoJson] = useState(null);
  const [electionsState, setElectionsState] = useState("idle");
  const [elections, setElections] = useState([]);

  useEffect(() => {
    setSelectedCode(toMapRegionCode(initialSelectedRegionCode));
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

  const mapLabels = useMemo(
    () =>
      features
        .map((feature) => {
          const regionCode = feature?.properties?.region_code;
          const projectedFeature = projected.get(regionCode);
          if (!regionCode || !projectedFeature) return null;

          const offset = LABEL_OFFSETS[regionCode] || { x: 0, y: 0 };
          return {
            code: regionCode,
            text: REGION_SHORT_LABELS[regionCode] || feature?.properties?.region_name || regionCode,
            x: projectedFeature.center.x + offset.x,
            y: projectedFeature.center.y + offset.y,
            optional: DENSE_LABEL_CODES.has(regionCode)
          };
        })
        .filter(Boolean),
    [features, projected]
  );

  const activeCode = selectedCode || focusedCode || hoveredCode;
  const activePrefix = regionPrefix(activeCode);
  const activeApiCode = toApiRegionCode(activeCode);
  const selectedApiCode = toApiRegionCode(selectedCode);
  const activeFeature = features.find((feature) => feature.properties.region_code === activeCode) || null;
  const activeLatest = activeCode ? latestByRegion.get(activeCode) || null : null;
  const activeRegionName = activeFeature?.properties?.region_name || (activePrefix ? REGION_PREFIX_LABELS[activePrefix] : activeCode);
  const modeLabel = selectedCode ? "선택 고정" : focusedCode ? "키보드 포커스" : hoveredCode ? "hover 미리보기" : "대기";
  const activeFreshness = freshnessBadge(activeLatest?.freshness_hours);
  const activeSample = sampleBadge(activeLatest?.sample_size);

  useEffect(() => {
    if (!selectedApiCode) {
      setElections([]);
      setElectionsState("idle");
      return;
    }
    let cancelled = false;
    const loadElections = async () => {
      setElectionsState("loading");
      try {
        const res = await fetch(`${apiBase}/api/v1/regions/${encodeURIComponent(selectedApiCode)}/elections`, { cache: "no-store" });
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
  }, [apiBase, selectedApiCode]);

  const electionsForRegion = useMemo(() => {
    const selectedPrefix = regionPrefix(selectedCode);
    if (!selectedPrefix) return [];
    return elections.filter((item) => regionPrefix(item.region_code) === selectedPrefix);
  }, [elections, selectedCode]);

  const excludedMismatchCount = Math.max(0, elections.length - electionsForRegion.length);

  const slotItems = useMemo(
    () =>
      SLOT_ORDER.map((slotKey) => {
        const candidates = electionsForRegion.filter((item) => normalizeOfficeType(item.office_type) === slotKey);
        const election = chooseRepresentative(candidates);
        const status = slotStatus({ electionsState, election });
        const title = buildSlotTitle({
          slotKey,
          regionName: activeRegionName,
          regionCode: selectedCode,
          election
        });
        const hrefId = election?.latest_matchup_id || election?.matchup_id || null;
        const href = hrefId && !String(hrefId).startsWith("master|") ? `/matchups/${encodeURIComponent(hrefId)}` : null;
        return {
          slotKey,
          slotLabel: SLOT_LABELS[slotKey],
          title,
          election,
          status,
          href
        };
      }),
    [activeRegionName, electionsForRegion, electionsState, selectedCode]
  );

  return (
    <section className="panel region-layout">
      <div className="map-shell">
        <div className="map-canvas">
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
            {mapLabels.map((label) => {
              const isActive = activeCode === label.code;
              return (
                <text
                  key={label.code}
                  x={label.x}
                  y={label.y}
                  className={`map-label ${label.optional ? "optional" : ""} ${isActive ? "active" : ""}`}
                  textAnchor="middle"
                  dominantBaseline="central"
                >
                  {label.text}
                </text>
              );
            })}
          </svg>
        ) : null}
        </div>
        <div className="map-guide">
          <p className="guide-title">지도 읽기 가이드</p>
          <div className="badge-row">
            <span className="state-badge info">연한 청록: 최신 조사 있음</span>
            <span className="state-badge warn">회색: 최신 조사 없음</span>
            <span className="state-badge ok">진한 청록: 현재 선택</span>
          </div>
          <p className="muted-text">데스크톱은 hover 미리보기 + click 고정, 모바일은 tap으로 고정 선택합니다.</p>
        </div>
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

        <div className="region-block region-guide-block">
          <strong>빠른 확인 순서</strong>
          <p className="muted-text">1) 지역 선택 상태 확인 → 2) 최신 조사/신선도 확인 → 3) 연결 선거 슬롯에서 상세 이동</p>
        </div>

        {!activeCode ? <div className="empty-state">지역을 선택해 주세요.</div> : null}

        {activeCode ? (
          <div className="region-block region-summary-block">
            <p className="region-name">{activeRegionName || activeCode}</p>
            <p className="region-code">{activeApiCode || activeCode}</p>
            <div className="badge-row region-summary-row">
              <span className={`state-badge ${activeLatest ? "ok" : "info"}`}>{modeLabel}</span>
              <span className={`state-badge ${activeLatest ? "ok" : "warn"}`}>{activeLatest ? "최신 조사 있음" : "최신 조사 없음"}</span>
              <span className={`state-badge ${activeFreshness.tone}`}>{activeFreshness.text}</span>
              <span className={`state-badge ${activeSample.tone}`}>{activeSample.text}</span>
            </div>
          </div>
        ) : null}

        {activeLatest ? (
          <div className="region-block">
            <strong>{activeLatest.title}</strong>
            <p>대표값: {formatPercent(activeLatest.value_mid)}</p>
            <dl className="region-meta-grid">
              <div>
                <dt>최신 조사일</dt>
                <dd>{formatDate(activeLatest.survey_end_date)}</dd>
              </div>
              <div>
                <dt>조사기관</dt>
                <dd>{activeLatest.pollster || "조사기관 미확인"}</dd>
              </div>
              <div>
                <dt>표본</dt>
                <dd>{formatSampleMeta(activeLatest.sample_size)}</dd>
              </div>
              <div>
                <dt>오차</dt>
                <dd>{formatMarginMeta(activeLatest.margin_of_error || activeLatest.moe)}</dd>
              </div>
              <div>
                <dt>채널</dt>
                <dd>{joinChannels(activeLatest.source_channels)}</dd>
              </div>
            </dl>
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

        {selectedApiCode ? (
          <div className="region-block">
            <div className="region-slot-head">
              <strong>연결 선거 (광역 3슬롯 고정)</strong>
              <p className="muted-text">단체장 → 의회 → 교육감 순서로 고정 노출합니다.</p>
            </div>
            {excludedMismatchCount > 0 ? (
              <p className="slot-note warn">선택 지역과 다른 코드 {excludedMismatchCount}건은 표시에서 제외했습니다.</p>
            ) : null}
            <ul className="region-slot-list">
              {slotItems.map((slot) => (
                <li key={slot.slotKey} className="slot-card">
                  <div className="slot-card-head">
                    <strong>{slot.slotLabel}</strong>
                    <span className={`state-badge ${slot.status.tone}`}>{slot.status.text}</span>
                  </div>
                  <p className="slot-title">{slot.title}</p>
                  <p className="muted-text">최신 조사일: {formatDate(slot.election?.latest_survey_end_date)}</p>
                  <div className="badge-row">
                    {slot.election?.is_placeholder ? <span className="state-badge warn">placeholder</span> : null}
                    {slot.election?.has_candidate_data ? <span className="state-badge info">후보 데이터 있음</span> : null}
                  </div>
                  {slot.href ? (
                    <Link href={slot.href} className="text-link small">
                      매치업 상세 보기
                    </Link>
                  ) : (
                    <span className="muted-text">매치업 상세 없음</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </aside>
    </section>
  );
}
