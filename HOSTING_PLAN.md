# Cloudflare 연결 시험 계획 (2026-09-15)

Issue: edwardkim/rhwp#7159. 사용자의 다음 작업 진행 승인 범위.

- Wrangler 4.131.2를 lockfile로 고정, 설치 단계에는 토큰 없음.
- 검증된 ZIP을 빈 임시 디렉터리에 추출, 앱은 공용 assets preview branch에 먼저 배포. 고유 URL의 build.json과 WASM MIME/bytes를 확인한다. PR 코드는 실행하지 않는다.
- live head/CI attempt를 재확인한 뒤 trusted 정적 진입 페이지를 pr-N 또는 production devel에 배포. 진입 페이지는 검증한 고유 URL로 이동하며 no-store. 고유 배포는 뒤늦게 이전 작업이 완료되어도 불변이다.
- Pages API의 관리 marker metadata에 asset ID, SHA, 최초 성공 시의 PR base SHA/배포 ID를 기록. GitHub 댓글은 상태의 정본이 아니다.
- 첫 baseline은 PR의 base SHA에 해당하는 검증된 devel 배포가 있을 때만 허용. 없으면 보류. 해당 SHA를 임의로 current devel로 대체하지 않는다.
- 새 포인터 HTTPS 확인 후 댓글 갱신. 실패 시 기존 고유 URL을 보존·표시. 최신 head와 다름을 명시.
- 재조정 시 전체 최신 포인터와 baseline을 참조 추적. 종료된 PR 포인터와 참조 없는 관리 배포만 삭제. 사용자 수동 배포는 관리 marker가 없으므로 보존.
- 삭제 직전 GitHub 요청 snapshot 재확인; 변경 시 cleanup 중단. 별칭 preview force 삭제는 실제 ID와 재조회로 증명. production canonical은 삭제 금지.
- 한 실행 생성 최대 12개, 총 관리 배포 100개 상한, API/HTTP timeout. 자동 provider 재시도는 업로드 중복 가능성이 있어 목록 재조회로 복구.
- 행렬: devel 최초, PR 최초/연속 push/force-push, Quality 실패, 수동 중복, devel 이동과 baseline 보존, close/reopen 및 이전 ID 제거. fork는 별도 작성자 권한 확보 전 미검증으로 남김.

현재 공개 rhwp 수동 배포는 고유 URL로 보존한다. 시험 프로젝트 root는 이 시험의 devel WASM 앱으로 바뀐다. rhwp 운영 저장소는 변경하지 않는다.

## Fork 게시 승인 추가 (2026-09-15)

사용자 승인: fork 미리보기의 SHA별 게시 승인 추가를 진행한다.
- Lab Preview 수동 실행의 PR 번호와 전체 approve_sha로 한 실행만 승인한다. actor와 rerun triggering_actor 모두 현재 write/maintain/admin 권한을 확인한다.
- 승인 범위는 PR 번호·head repository ID·전체 SHA. 배포 직전 live identity와 권한을 재조회한다. 자동 이벤트·다른 PR·새 head에 승인 승계 없음.
- 승인은 영구 저장하지 않는다. 동일 SHA도 별도 수동 재게시에는 다시 명시한다. 대기 concurrency가 취소한 승인 실행은 재요청해야 한다.
- fork CI 성공 후 승인 없으면 게시 대기, 이전 정상 고유 링크 유지. 내부 PR/devel 자동 게시 유지.
- fork 고정 주소에는 자동 이동 대신 외부 기여 코드/민감 문서 주의 안내와 열기 링크를 표시한다. 코드 안전성 보증이나 외부 통신 차단으로 표현하지 않는다.
- 로컬 권한·head 변경 계약 테스트와 내부 PR 회귀 실행 후 실제 별도 계정 fork 시험을 이어간다.

## 실제 Studio 연결 시험 (2026-09-15)

사용자 승인으로 `Studio Preview Probe` 수동 workflow를 추가한다. source repository는 edwardkim/rhwp로 고정하며 devel 또는 명시한 PR의 live head를 선택한다. trusted rhwp classifier/policy/evidence 모듈은 devel 0c9e28a481e662ff3b1823cfb1814084a13eb58b에서 가져왔다. 전체 CI audit 뒤 read-only release 빌드를 하고, 새 publisher job에서 gate와 SHA를 재조회한다. fork 소스 빌드 job에 배포 secret 또는 write permission을 주지 않는다.

실제 제품은 `studio-devel`/`studio-pr-N` branch와 `rhwp-studio-probe:v1:` metadata namespace로 구분한다. 기존 최소 WASM 시험과 서로 배포를 삭제하지 않는다. 기존 CI dev/merge 산출물은 재사용하지 않으며 전용 release/npm cache를 복원하고 devel만 저장한다. 이 수동 시험은 rhwp 운영 trigger 활성화가 아니다.

보안 보정: workflow_dispatch(main)에서 외부 PR 코드를 빌드하면 Actions runtime cache도 main 범위일 수 있다. 수동 실제-source probe는 cache restore/save를 모두 하지 않는다. PR별 격리 cache 재사용은 운영 pull_request 이벤트 배선에서만 적용한다.
