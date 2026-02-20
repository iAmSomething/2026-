import Link from "next/link";

import { fetchApi } from "../../_lib/api";

export default async function CandidatePage({ params }) {
  const resolvedParams = await params;
  const candidateId = resolvedParams.candidate_id;
  const payload = await fetchApi(`/api/v1/candidates/${encodeURIComponent(candidateId)}`);

  return (
    <main>
      <h1 style={{ marginTop: 0 }}>Candidate Route RC</h1>
      <p>candidate_id: {candidateId}</p>
      <p>
        <Link href="/">Back to /</Link>
      </p>
      <p>api_status: {payload.status}</p>
      <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(payload.body, null, 2)}</pre>
    </main>
  );
}
