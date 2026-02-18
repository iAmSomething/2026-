const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8100';

async function getSummary() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/dashboard/summary`, { cache: 'no-store' });
    if (!res.ok) {
      return { error: `summary status ${res.status}` };
    }
    return await res.json();
  } catch (err) {
    return { error: err instanceof Error ? err.message : 'unknown error' };
  }
}

export default async function Home() {
  const summary = await getSummary();
  const hasError = Boolean(summary.error);

  return (
    <main>
      <h1 style={{ marginTop: 0 }}>Election 2026 Staging</h1>
      <p>API Base: {API_BASE}</p>
      {hasError ? (
        <p style={{ color: '#b91c1c' }}>summary fetch failed: {summary.error}</p>
      ) : (
        <>
          <p>party_support count: {Array.isArray(summary.party_support) ? summary.party_support.length : 0}</p>
          <p>
            presidential_approval count:{' '}
            {Array.isArray(summary.presidential_approval) ? summary.presidential_approval.length : 0}
          </p>
        </>
      )}
    </main>
  );
}
