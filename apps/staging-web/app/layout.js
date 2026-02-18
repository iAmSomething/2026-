export const metadata = {
  title: 'Election 2026 Staging',
  description: 'FastAPI + Next.js staging smoke view'
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body style={{ fontFamily: 'system-ui, sans-serif', margin: 0, padding: '24px', background: '#f8fafc' }}>
        {children}
      </body>
    </html>
  );
}
