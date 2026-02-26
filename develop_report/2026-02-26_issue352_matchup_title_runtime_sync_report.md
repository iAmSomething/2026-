# 2026-02-26 issue352 matchup title runtime sync report

## 1. 이슈
- Issue: #352
- 제목: [DEVELOP][P0] #340 매치업 제목 정책 운영 반영(런타임 동기화)
- 목표: 매치업 상세에서 `h1`은 canonical 제목으로 고정하고, 기사형 제목은 부제로 분리 노출.

## 2. 변경 파일
1. `app/services/repository.py`
2. `app/models/schemas.py`
3. `apps/web/app/matchups/[matchup_id]/page.js`
4. `tests/test_repository_matchup_legal_metadata.py`
5. `tests/test_api_routes.py`

## 3. 구현 내용
1. API/Repository 제목 정책 반영
- `get_matchup()`에서 `matchups.title`을 canonical 제목으로 우선 사용.
- 응답 필드 추가:
  - `canonical_title`
  - `article_title`
- `title`은 canonical 제목으로 고정.
- 기사 제목이 canonical과 동일하면 `article_title`은 `null`로 정규화.

2. 웹 런타임 렌더링 정책 반영 (`apps/web`)
- 매치업 상세 상단:
  - `h1`: `canonical_title` 우선, 없으면 `title`, 최후 `matchup_id`
  - 부제: `article_title`이 있고 canonical과 다를 때만 `기사 제목: ...`로 노출

3. 계약 테스트 보강
- repository 테스트에서 canonical/meta 제목과 observation 제목이 다를 때 분리 저장/응답을 검증.
- API 계약 테스트에서 `canonical_title`, `article_title` 키 존재 검증.

## 4. 검증 로그
1. Python/pytest (3.13)
- 명령:
```bash
source .venv313/bin/activate && pytest tests/test_repository_matchup_legal_metadata.py tests/test_repository_matchup_scenarios.py tests/test_api_routes.py
```
- 결과: `28 passed`

2. Web build (`apps/web`)
- 명령:
```bash
npm --prefix apps/web run build
```
- 결과: 성공 (`/matchups/[matchup_id]` 포함)

3. 런타임/환경 메모
- Python 3.14에서는 `pydantic-core` 빌드 이슈로 실패 확인.
- 동일 설치를 Python 3.13 가상환경(`.venv313`)에서 성공 확인.

## 5. 배포 경로 일치 근거
- CI 배포 워크플로: `.github/workflows/vercel-preview.yml`
- `root_dir` 허용값/기본값: `apps/web` 단일
- deploy 단계는 repo root에서 `vercel deploy` 수행(프로젝트 rootDirectory 중복 방지 주석 포함)

## 6. 남은 운영 확인 항목
- main 반영 후 운영 URL 실증(요구사항):
  1. before/after 캡처 2건 이상
  2. `h1=canonical` + `부제=기사 제목` 동시 확인
