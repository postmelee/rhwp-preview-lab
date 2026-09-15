# 실제 rhwp Studio 배포 검증 (2026-09-15)

실제 PR/devel source의 Linux release WASM과 Studio를 Cloudflare에 배포했다. 이 저장소의 **수동 probe**이며 운영 rhwp의 자동 갱신은 아직 활성화하지 않았다.

| 대상 | SHA | 링크 |
| --- | --- | --- |
| PR #7118 | `c0f80c0ac6eb249bf1fb82a8f954b7035e15bb53` | [PR head 안내](https://studio-pr-7118.rhwp-preview-lab.pages.dev) |
| 고정 비교 기준 | `769582fc856f162e57604b318d41414d7b026345` | [base](https://531238ca.rhwp-preview-lab.pages.dev) |
| 관측 시점 devel | `4fddb1bb7244fb478ea18f927aca273f93ac7322` | [devel](https://studio-devel.rhwp-preview-lab.pages.dev) |

- [PR 빌드](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34949858736): head/base release 성공, 최초 publish는 HTML canonical 경로 처리로 실패.
- [수정된 PR 게시](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34952019828): 기존 JS/WASM 재사용, 정확한 source 폰트 재포장 및 provenance/digest 검증 후 성공. 59 files, 45,016,750 bytes.
- [devel 전체 빌드/게시](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34951384000): 수정된 폰트 복사·HTML 경로 검사를 포함한 전체 실행 성공. 59 files, 45,073,314 bytes.
- [오래된 devel 복구 차단](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34951012392): source 0c9e28a 이후 devel 이동을 감지하여 별칭 게시를 거부했다.

PR에서 `Preview PR 7118 roundtrip` 입력 → HWPX 저장 → 새 문서 → 최근 문서 재열기 → 실제 렌더링을 확인했다. 7,363-byte 저장 파일의 section XML도 일치한다. 브라우저 semantic click 대신 native 버튼 클릭으로 저장 picker를 열었으며 생성한 시험 파일만 이번에 열도록 허용했다. [재열기 화면](evidence/studio-stage3/pr-reopened.jpg), [증적](evidence/studio-stage3/browser-result.json).

devel은 초기화·입력·렌더링, base는 초기화·표시 SHA까지만 확인했다. 모든 편집 기능이나 한컴 조판 일치 검증은 아니다.

GitHub `queue: max` 최소 실행 [34952976700](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34952976700), [34952986054](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34952986054), [34952995462](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34952995462)도 모두 성공했다. 기본 pending 교체를 피하지만 최대 100개 이후 취소될 수 있다.

## 운영 후보와의 차이

lab 수동 probe는 고정된 실제-source 시험이다. 운영 후보는 외부 head를 main 이벤트에서 실행하지 않고 native pull_request producer와 trusted publisher로 분리했다. PR artifact를 devel/base로 재사용하지 않으며 build recipe가 다른 asset도 재사용하지 않는다. 최종 후보는 rhwp 격리 worktree의 로컬 commit e96cf1053에만 있다.

다음 검증은 최종 native producer/controller의 결합 실행이다. 이 문서의 수동 실제-source probe나 이전 fixture fork lifecycle을 최종 운영 workflow E2E 성공으로 확장하지 않는다. rhwp 운영 push/PR/설정 변경은 아직 하지 않았다.
