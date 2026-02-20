import Link from "next/link";

import { fetchApi } from "../../_lib/api";

export default async function MatchupPage({ params }) {
  const resolvedParams = await params;
  const matchupId = resolvedParams.matchup_id;
  const payload = await fetchApi(`/api/v1/matchups/${encodeURIComponent(matchupId)}`);

  return (
    <main>
      <h1 style={{ marginTop: 0 }}>Matchup Route RC</h1>
      <p>matchup_id: {matchupId}</p>
      <p>
        <Link href="/">Back to /</Link>
      </p>
      <p>api_status: {payload.status}</p>
      <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(payload.body, null, 2)}</pre>
    </main>
  );
}
