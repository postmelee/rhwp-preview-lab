# Cloudflare 시험 운영 상태

2026-09-15: Direct Upload 프로젝트와 GitHub Secret/Variables 연결 완료. 시험용 자동 publisher는 `lab/publish.py`, provider는 `lab/hosting.py`다. rhwp 운영 CI는 아직 변경하지 않았다.

## 주소와 빌드

- 시험 devel: https://rhwp-preview-lab.pages.dev (최소 WASM 시험 앱)
- 기존 실제 rhwp Studio 수동 배포: https://882d9256.rhwp-preview-lab.pages.dev
- PR 주소는 `pr-N` 별칭이다. 실제 API 별칭과 응답 확인 후 코멘트에 공개한다.
- 실제 rhwp release artifact와 최소 WASM lifecycle fixture를 혼동하지 않는다. rhwp에 이식할 때 동일 provider에 실제 Studio artifact를 연결한다.

## 신뢰 경계

- main의 trusted publisher만 `CLOUDFLARE_API_TOKEN`을 받는다. 설치 단계·PR CI·브라우저 검증에는 전달하지 않는다.
- 고정 Wrangler 4.131.2와 lockfile을 사용한다. 빈 임시 작업 디렉터리에서 정적 ZIP만 배포하며 Functions/worker 코드는 ZIP gate에서 거절한다.
- 필수 CI 현재 head/run/attempt·GitHub digest·ZIP 계약을 확인한다. 앱 고유 URL에 먼저 업로드하고 public bytes/WASM MIME 검사 후 live head를 다시 조회해 고정 주소를 연결한다. 배포 job은 artifact JS/WASM을 실행하지 않는다.
- 포인터는 정적 HTML 이동 페이지다. PR 고정 주소에서 검증된 고유 URL로 이동하므로 브라우저 주소가 바뀐다. 비교 기준은 이 고유 배포 ID와 SHA로 고정한다.
- metadata marker가 있는 배포만 관리한다. 현재 PR/devel 포인터와 참조 중인 baseline은 보존한다. 실패가 있는 재조정에서는 정리를 보류한다. 한 실행 생성 12개·관리 배포 100개 상한으로 무한 축적을 차단한다.
- 최신 preview 별칭은 DELETE force 옵션으로 정리한다. production canonical과 marker 없는 수동 배포는 보호한다. 실제 삭제 후 목록을 다시 확인한다.

## 설정·복구

- Secret: `CLOUDFLARE_API_TOKEN`. Variables: `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_PROJECT`.
- 현재 계정 토큰 `rhwp-preview-lab-ci`: 계정 Pages Write, UI 표시 만료 2026-10-16. 특정 프로젝트 전용 토큰이 아니다.
- trial destination은 `rhwp-preview-lab`으로 코드에서 제한한다. production branch는 API로 `devel` 설정 및 재조회한다.
- Actions의 Lab Preview 수동 실행은 기존 성공 artifact를 재사용한다. 실패 CI를 우회하지 않는다. 재빌드는 해당 CI rerun이다.
- `workflow_run`은 default main, `pull_request_target: closed`는 base devel의 workflow 정의를 사용한다. 두 branch에 trusted publisher 배선이 필요하다.
- 공개 probe는 명시적 `rhwp-preview-lab/2` User-Agent를 사용한다. 기본 Python 식별자는 실측 HTTP 403/1010이었다.
- 필요 시 Lab Preview workflow를 disable한다. 토큰 폐기·갱신은 Cloudflare UI에서 하며 값을 문서·채팅에 기록하지 않는다.

## 남은 검증 경계

fork 성공은 내부 PR 성공과 다르다. 별도 작성자 계정의 정상 fork PR과 maintainer 승인 경로가 아직 필요하다. rhwp 전체 gate 이식, 실제 Studio 저장·재열기 및 운영 main 활성화는 별도 단계다. 동일 PR이 종료되어 배포가 정리된 뒤 reopen하면 새 미리보기 수명으로 baseline을 다시 고정한다.

공식 근거: [Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/), [CI 연동](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/), [삭제 API](https://developers.cloudflare.com/api/resources/pages/subresources/projects/subresources/deployments/methods/delete/).


## Fork 게시 승인

Lab Preview의 Run workflow에서 branch `main`, `pr` 번호, `approve_sha`에 현재 전체 40자리 head SHA를 입력한다. fork CI 실행 승인은 GitHub의 기존 정책을 따르며, 이 입력은 CI 승인을 대체하거나 실패 CI를 우회하지 않는다.

actor와 재실행 triggering_actor 모두 현재 write/maintain/admin 권한이 있어야 한다. 승인은 PR 번호·fork 저장소 ID·SHA와 해당 실행에만 유효하다. 영구 승인 라벨/댓글을 사용하지 않으며, 새 push와 이후 수동 재게시에는 다시 명시한다. 직렬화 대기 중 취소된 승인 실행도 자동 승계하지 않는다.

승인 없는 fork는 성공 CI 확인 후 게시 대기로 표시하고 기존 정상 고유 링크를 유지한다. 내부 PR/devel은 자동 게시한다. fork 고정 주소는 자동 이동 대신 외부 코드/민감 문서 주의 안내와 열기 링크를 표시한다. 이는 게시 통제이며 악성 코드 판정이나 외부 통신 차단 기능이 아니다.

실제 별도 작성자 fork 시험은 아직 미완료다. SHA 변경·권한 회수·다른 PR/저장소·승인 누락은 로컬 계약 테스트로 확인했다.
