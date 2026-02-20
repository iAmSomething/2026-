export const API_BASE =
  process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "https://2026-api-production.up.railway.app";

export async function fetchApi(path) {
  const url = `${API_BASE}${path}`;
  try {
    const res = await fetch(url, { cache: "no-store" });
    const text = await res.text();
    let body;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = { raw: text };
    }
    if (!res.ok) {
      return { ok: false, status: res.status, body, url };
    }
    return { ok: true, status: res.status, body, url };
  } catch (err) {
    return {
      ok: false,
      status: 0,
      body: { error: err instanceof Error ? err.message : "unknown error" },
      url
    };
  }
}
