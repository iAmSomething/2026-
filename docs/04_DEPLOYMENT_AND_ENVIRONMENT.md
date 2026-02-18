# 배포 및 개발 환경 명세

- 문서 버전: v0.2
- 최종 수정일: 2026-02-18
- 수정자: Codex

## 1. 최종 배포 아키텍처
1. DB: Supabase Postgres
2. API/배치: FastAPI (Python)
3. 웹 프론트: Next.js
4. 권장 배포 경로:
- 웹: Vercel
- API/배치: Railway
- DB/스토리지: Supabase

## 2. 컴포넌트 책임
1. Supabase
- 정규화 데이터 저장
- 접근 제어(RLS)
- 백업/모니터링
2. FastAPI
- 공개 API 제공
- 기사 수집/추출/검증 배치 실행
- 검수용 내부 API 제공
3. Next.js
- 대시보드/검색/상세 UI 렌더링
- API 데이터 시각화

## 3. 개발 환경 원칙 (가상환경 필수)
1. 로컬 Python 패키지는 프로젝트 가상환경(`.venv`)에서만 설치/실행
2. 시스템 Python 전역 설치 금지
3. 실행 예시:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. 비밀키 정책
1. `key.txt`는 로컬 전용 파일
2. `key.txt` 절대 커밋 금지 (`.gitignore` 반영)
3. 운영에서는 플랫폼 Secret으로 주입
4. `.env` 파일도 커밋 금지

## 5. Data.go.kr API 활용 설계
### 필수
1. `CommonCodeService`
2. `PofelcddInfoInqireService`

### 선택
1. `WinnerInfoInqireService2`
2. `VoteXmntckInfoInqireService2`
3. `PartyPlcInfoInqireService`

## 6. 네트워크/보안
1. 프론트는 공개 API만 접근
2. 내부 운영 API는 별도 토큰/권한으로 분리
3. 관리자 승인 API는 서버-서버 통신만 허용

## 7. 배포 전략
1. `main` 기준 자동 배포
2. 배포 전 체크:
- 마이그레이션 적용 가능 여부
- 필수 Secret 주입 여부
- 공개 API 헬스체크
3. 롤백:
- API 컨테이너 이전 버전 롤백
- DB는 롤백 SQL 또는 스냅샷 복구 기준 운영
