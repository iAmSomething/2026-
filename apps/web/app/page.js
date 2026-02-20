import Link from "next/link";

import { API_BASE, fetchApi } from "./_lib/api";

export default async function HomePage() {
  const summary = await fetchApi("/api/v1/dashboard/summary");

  return (
    <main>
      <h1 style={{ marginTop: 0 }}>Election 2026 Public Web RC</h1>
      <p>API Base: {API_BASE}</p>
      <ul>
        <li>
          <Link href="/matchups/m_2026_seoul_mayor">/matchups/m_2026_seoul_mayor</Link>
        </li>
        <li>
          <Link href="/candidates/cand-jwo">/candidates/cand-jwo</Link>
        </li>
      </ul>
      {summary.ok ? (
        <div>
          <p>summary status: {summary.status}</p>
          <p>party_support count: {Array.isArray(summary.body?.party_support) ? summary.body.party_support.length : 0}</p>
          <p>
            presidential_approval count:{" "}
            {Array.isArray(summary.body?.presidential_approval) ? summary.body.presidential_approval.length : 0}
          </p>
        </div>
      ) : (
        <div>
          <p style={{ color: "#b91c1c" }}>summary fetch failed: status {summary.status}</p>
          <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(summary.body, null, 2)}</pre>
        </div>
      )}
    </main>
  );
}
