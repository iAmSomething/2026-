export const API_BASE =
  process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "https://2026-api-production.up.railway.app";

const APP_ENV = (process.env.APP_ENV || process.env.NODE_ENV || "development").toLowerCase();
const VERCEL_ENV = (process.env.VERCEL_ENV || "").toLowerCase();

export function isFixtureFallbackAllowed() {
  if (VERCEL_ENV === "production" || VERCEL_ENV === "preview") return false;
  return ["local", "dev", "development", "test"].includes(APP_ENV);
}

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

export async function loadJsonFixture(relativePath) {
  if (!isFixtureFallbackAllowed()) {
    return null;
  }
  try {
    const { readFile } = await import("node:fs/promises");
    const { join } = await import("node:path");
    const fixturePath = join(process.cwd(), "public", relativePath);
    const raw = await readFile(fixturePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}
