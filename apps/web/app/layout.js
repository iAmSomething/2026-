import Link from "next/link";

import "./globals.css";

export const metadata = {
  title: "Election 2026 Dashboard",
  description: "2026 선거 여론조사 대시보드"
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>
        <header className="site-header">
          <div className="site-header-inner">
            <Link href="/" className="brand">
              2026 Elections
            </Link>
            <nav className="site-nav">
              <Link href="/">대시보드</Link>
              <Link href="/search">지역 검색</Link>
              <Link href="/matchups/m_2026_seoul_mayor">매치업</Link>
              <Link href="/candidates/cand-jwo">후보</Link>
            </nav>
          </div>
        </header>
        <div className="page-shell">{children}</div>
      </body>
    </html>
  );
}
