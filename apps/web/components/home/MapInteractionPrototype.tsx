"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { MapLatestRegion } from "@/lib/types/api";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatMetaLine } from "@/lib/format/meta";
import { formatPercent } from "@/lib/format/percent";

type Props = {
  regions: MapLatestRegion[];
  initialSelectedRegionCode?: string | null;
};

type GeoPoint = [number, number];
type PolygonCoordinates = GeoPoint[][];
type MultiPolygonCoordinates = GeoPoint[][][];

type GeoFeature = {
  type: "Feature";
  properties: {
    region_code: string;
    region_name: string;
  };
  geometry: {
    type: "Polygon" | "MultiPolygon";
    coordinates: PolygonCoordinates | MultiPolygonCoordinates;
  };
};

type GeoJsonCollection = {
  type: "FeatureCollection";
  features: GeoFeature[];
};

type ProjectedPolygon = Array<Array<{ x: number; y: number }>>;

type ProjectResult = {
  path: string;
  center: { x: number; y: number };
};

function getFeatureLonLatPoints(feature: GeoFeature): GeoPoint[] {
  if (feature.geometry.type === "Polygon") {
    return (feature.geometry.coordinates as PolygonCoordinates).flat();
  }
  return (feature.geometry.coordinates as MultiPolygonCoordinates).flat(2);
}

function projectFeaturePoints(
  feature: GeoFeature,
  project: (point: GeoPoint) => { x: number; y: number }
): ProjectedPolygon {
  if (feature.geometry.type === "Polygon") {
    return (feature.geometry.coordinates as PolygonCoordinates).map((ring) => ring.map((point) => project(point)));
  }
  const polygons = feature.geometry.coordinates as MultiPolygonCoordinates;
  return polygons.flatMap((polygon) => polygon.map((ring) => ring.map((point) => project(point))));
}

function ringsToPath(rings: ProjectedPolygon): string {
  return rings
    .map((ring) => {
      if (ring.length === 0) return "";
      const [start, ...rest] = ring;
      const commands = [`M ${start.x.toFixed(2)} ${start.y.toFixed(2)}`];
      for (const point of rest) commands.push(`L ${point.x.toFixed(2)} ${point.y.toFixed(2)}`);
      commands.push("Z");
      return commands.join(" ");
    })
    .join(" ");
}

function toProjectResult(feature: GeoFeature, project: (point: GeoPoint) => { x: number; y: number }): ProjectResult {
  const projectedRings = projectFeaturePoints(feature, project);
  const path = ringsToPath(projectedRings);
  const points = projectedRings.flat();
  const center = points.reduce(
    (acc, point) => ({ x: acc.x + point.x / Math.max(points.length, 1), y: acc.y + point.y / Math.max(points.length, 1) }),
    { x: 0, y: 0 }
  );
  return { path, center };
}

export function MapInteractionPrototype({ regions, initialSelectedRegionCode }: Props) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(initialSelectedRegionCode || null);
  const [focused, setFocused] = useState<string | null>(null);
  const [touchMode, setTouchMode] = useState(false);
  const [geoState, setGeoState] = useState<"loading" | "ready" | "error">("loading");
  const [geoJson, setGeoJson] = useState<GeoJsonCollection | null>(null);

  useEffect(() => {
    setSelected(initialSelectedRegionCode || null);
  }, [initialSelectedRegionCode]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const media = window.matchMedia("(hover: none), (pointer: coarse)");
    const apply = () => setTouchMode(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    let mounted = true;
    const loadGeoJson = async () => {
      setGeoState("loading");
      try {
        const res = await fetch("/geo/kr_adm1_simplified.geojson", { cache: "no-store" });
        if (!res.ok) throw new Error(`geojson status ${res.status}`);
        const data = (await res.json()) as GeoJsonCollection;
        if (!mounted) return;
        setGeoJson(data);
        setGeoState("ready");
      } catch {
        if (!mounted) return;
        setGeoState("error");
      }
    };
    void loadGeoJson();
    return () => {
      mounted = false;
    };
  }, []);

  const regionMap = useMemo(() => new Map(regions.map((region) => [region.region_code, region])), [regions]);
  const features = useMemo(() => geoJson?.features ?? [], [geoJson]);

  const projectedMap = useMemo(() => {
    if (features.length === 0) return new Map<string, ProjectResult>();
    const lonLatPoints = features.flatMap((feature) => getFeatureLonLatPoints(feature));
    const lons = lonLatPoints.map((point) => point[0]);
    const lats = lonLatPoints.map((point) => point[1]);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const width = 820;
    const height = 960;
    const padding = 24;

    const project = ([lon, lat]: GeoPoint) => {
      const safeLonRange = Math.max(maxLon - minLon, 0.1);
      const safeLatRange = Math.max(maxLat - minLat, 0.1);
      const x = padding + ((lon - minLon) / safeLonRange) * (width - padding * 2);
      const y = padding + ((maxLat - lat) / safeLatRange) * (height - padding * 2);
      return { x, y };
    };

    return new Map(features.map((feature) => [feature.properties.region_code, toProjectResult(feature, project)]));
  }, [features]);

  const activeRegionCode = selected || (!touchMode ? hovered : null) || focused || null;
  const active = activeRegionCode ? regionMap.get(activeRegionCode) ?? null : null;
  const activeFeature = activeRegionCode ? features.find((feature) => feature.properties.region_code === activeRegionCode) ?? null : null;

  const onSelectRegion = (regionCode: string) => {
    setSelected((prev) => (prev === regionCode ? null : regionCode));
  };

  return (
    <Card title="광역 지도 인터랙션 (GeoJSON)">
      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <div className="rounded-lg border border-slate-200 bg-white p-2">
          {geoState === "loading" ? <Skeleton className="h-[420px] w-full" /> : null}
          {geoState === "error" ? <ErrorState message="GeoJSON 지도를 불러오지 못했습니다." /> : null}
          {geoState === "ready" ? (
            <>
              <svg viewBox="0 0 820 960" role="img" aria-label="대한민국 광역 지도" className="h-[420px] w-full rounded-md bg-slate-50">
                {features.map((feature) => {
                  const regionCode = feature.properties.region_code;
                  const region = regionMap.get(regionCode);
                  const projected = projectedMap.get(regionCode);
                  if (!projected) return null;

                  const isActive = activeRegionCode === regionCode;
                  const hasData = region?.has_data ?? false;
                  const baseFill = isActive ? "#CCFBF1" : hasData ? "#E6FFFA" : "#E2E8F0";
                  const stroke = isActive ? "#0F766E" : "#64748B";
                  const labelColor = isActive ? "#0F766E" : "#334155";

                  return (
                    <g
                      key={regionCode}
                      role="button"
                      tabIndex={0}
                      aria-label={`${feature.properties.region_name}, ${hasData ? "데이터 있음" : "데이터 없음"}`}
                      aria-pressed={selected === regionCode}
                      onFocus={() => setFocused(regionCode)}
                      onBlur={() => setFocused((prev) => (prev === regionCode ? null : prev))}
                      onMouseEnter={() => {
                        if (!touchMode) setHovered(regionCode);
                      }}
                      onMouseLeave={() => {
                        if (!touchMode) setHovered((prev) => (prev === regionCode ? null : prev));
                      }}
                      onClick={() => onSelectRegion(regionCode)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          onSelectRegion(regionCode);
                        }
                      }}
                    >
                      <path d={projected.path} fill={baseFill} stroke={stroke} strokeWidth={isActive ? 2.8 : 1.6} />
                      <path d={projected.path} fill="none" stroke="transparent" strokeWidth={14} />
                      <text
                        x={projected.center.x}
                        y={projected.center.y}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fontSize={20}
                        fontWeight={700}
                        fill={labelColor}
                      >
                        {feature.properties.region_name}
                      </text>
                    </g>
                  );
                })}
              </svg>
              <p className="mt-2 text-xs text-slate-500">데스크톱: hover + click / 모바일: tap으로 선택 및 패널 갱신</p>
            </>
          ) : null}
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 fade-in" aria-live="polite">
          {!activeRegionCode ? (
            <div className="text-sm text-slate-600">
              {touchMode ? "지도에서 지역을 탭하면 상세 패널이 갱신됩니다." : "지도에서 지역을 클릭/오버하면 상세 패널이 갱신됩니다."}
            </div>
          ) : active ? (
            active.latest ? (
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <strong className="text-slate-800">{active.latest.title}</strong>
                  <Badge tone="ok">{active.latest.office_type}</Badge>
                </div>
                <p className="text-slate-700">대표값: {formatPercent(active.latest.value_mid)}</p>
                <p className="text-slate-500">{formatMetaLine(active.latest.pollster, active.latest.survey_end_date)}</p>
                <Link
                  href={`/matchups/${active.latest.matchup_id}`}
                  className="inline-block rounded-md bg-teal-700 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-teal-800"
                >
                  매치업 상세 보기
                </Link>
                {selected ? (
                  <button
                    type="button"
                    onClick={() => setSelected(null)}
                    className="ml-2 rounded-md border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700"
                  >
                    선택 해제
                  </button>
                ) : null}
              </div>
            ) : (
              <div className="text-sm text-slate-600">
                <p>선택 지역의 최신 데이터가 없습니다.</p>
                {activeFeature ? <p className="mt-1 text-xs text-slate-500">선택 지역: {activeFeature.properties.region_name}</p> : null}
              </div>
            )
          ) : (
            <div className="text-sm text-slate-600">
              <p>해당 지역은 현재 map-latest 데이터와 매핑되지 않았습니다.</p>
              {activeFeature ? <p className="mt-1 text-xs text-slate-500">선택 지역: {activeFeature.properties.region_name}</p> : null}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
