const REGION_PARAM_ALIASES = {
  "KR-11": "11-000",
  "KR-26": "26-000",
  "KR-41": "41-000"
};

const QUERY_ALIASES = {
  연수국: "연수구"
};

export function normalizeRegionParam(regionParam) {
  if (!regionParam || typeof regionParam !== "string") {
    return { input: "", normalized: null, corrected: false };
  }
  const trimmed = regionParam.trim();
  if (!trimmed) return { input: "", normalized: null, corrected: false };

  if (REGION_PARAM_ALIASES[trimmed]) {
    return {
      input: trimmed,
      normalized: REGION_PARAM_ALIASES[trimmed],
      corrected: true
    };
  }

  if (/^\d{2}(?:-\d{3})?$/.test(trimmed)) {
    return {
      input: trimmed,
      normalized: trimmed.length === 2 ? `${trimmed}-000` : trimmed,
      corrected: trimmed.length === 2
    };
  }

  return { input: trimmed, normalized: trimmed, corrected: false };
}

export function normalizeDemoQuery(query) {
  if (!query || typeof query !== "string") {
    return { input: "", normalized: "", corrected: false };
  }
  const trimmed = query.trim();
  if (!trimmed) return { input: "", normalized: "", corrected: false };
  const mapped = QUERY_ALIASES[trimmed] || trimmed;
  return {
    input: trimmed,
    normalized: mapped,
    corrected: mapped !== trimmed
  };
}

export function parseOnFlag(value) {
  if (typeof value !== "string") return false;
  const normalized = value.trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "on" || normalized === "yes";
}

export function toScenarioBadge(text, tone = "info") {
  return { text, tone };
}
