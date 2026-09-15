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
