# Cloudflare 연결 전 준비

현재 workflow는 Cloudflare API를 호출하지 않는다. 아래는 후속 설정안이며 적용 완료 상태가 아니다.

## 계정과 프로젝트

1. 사용자가 Cloudflare 계정을 만들고 로그인한다. token 값은 채팅·PR·로그에 붙이지 않는다.
2. Pages **Direct Upload** 시험 프로젝트를 준비한다. 기존 GitHub Actions에서 만든 산출물을 재사용하므로 Cloudflare Git 연동 빌드는 사용하지 않는다.
3. 프로젝트 production branch는 `devel`을 제안한다. 실제 확보된 project 이름과 `pages.dev` URL은 생성 후 API로 확인한다.
4. 전용 시험 계정에 한정한 `Account / Cloudflare Pages / Edit` token을 GitHub Actions secret에 저장한다. 계정 범위 권한이며 특정 프로젝트만 허용된다고 가정하지 않는다.
5. 제안 secret 이름 `CLOUDFLARE_API_TOKEN`, variable 이름 `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_PROJECT`. 현재 코드에는 아직 소비 배선이 없다.

## 연결 후 구현·시험

- trusted publisher만 token을 받는다. PR 빌드와 브라우저 시험 job에는 token을 전달하지 않는다.
- ZIP 검증 후 새 임시 폴더에 안전하게 추출하고, 고정 버전 Wrangler로 정적 파일만 업로드한다. 실행 위치의 `functions/`도 자동 업로드될 수 있으므로 게시 작업 폴더에는 함수 코드가 없어야 한다.
- 실제 WASM·폰트 MIME, HTTPS 기동, 파일 열기·편집·저장·재열기를 확인한다.
- PR별 고정 별칭, pinned baseline SHA, current devel URL을 코멘트 한 개에 표시한다. 새 버전 검증 전에는 기존 정상 배포를 삭제하지 않는다.
- 새 head 도착·역순 완료·배포 API 실패·중복 완료·close/reopen·공유 baseline 참조의 보존/정리를 실제 배포 ID와 별칭 재조회로 검증한다.
- Pages의 branch latest 배포 삭제 제한을 실제 확인한 후 종료 페이지 교체 여부를 정한다. 단순히 별칭이 갱신됐다는 사실로 이전 배포가 삭제됐다고 표시하지 않는다.
- static-only 시험이다. Functions, Workers 유료 플랜, R2를 자동 도입하지 않는다.

공식 근거(2026-09-15 확인): [Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/), [CI 연동](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/), [제한](https://developers.cloudflare.com/pages/platform/limits/).

## 별도 fork 시험

내부 PR 성공은 fork 성공 증거가 아니다. 다른 GitHub 작성자 계정/허가된 조직에서 만든 실제 fork가 필요하다. 계정 비밀번호나 token을 공유하지 않고 정상 fork PR과 maintainer 승인 경로로 검증한다.
