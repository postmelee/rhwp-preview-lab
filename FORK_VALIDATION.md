# 실제 fork PR 검증 — 2026-09-15

코드 SHA `c4681f4c257e1a18b960ac6e27510082ef1c84d4`를 수정 없이 검증했다. 작성자는 `thechoicesinmylife`, maintainer는 `postmelee`다. [시험 PR5](https://github.com/postmelee/rhwp-preview-lab/pull/5)는 devel 기준으로 만들었으며 합성 WASM 입력 `lab/case.json`만 바꿨다. 원본 저장소에서 작성자의 권한은 read, association은 FIRST_TIME_CONTRIBUTOR, head repository ID는 1371134782다.

| 항목 | 결과 | 실행 |
| --- | --- | --- |
| GitHub fork CI 승인 | first_time_contributors 정책에서 매 push 두 CI가 action_required. 승인 후 attempt 2 실행 | [첫 CI](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34947113000) |
| 승인 전 게시 차단 | CI가 모두 성공해도 게시 승인 대기 | [34947240818](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34947240818) |
| 첫 SHA 승인 | 94a1f4d97e88caa18a500e4c79f192c2374fcf97 게시. 외부 안내 후 링크를 클릭해 SHA와 WASM 42 확인 | [34947329827](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34947329827) |
| 새 push | 728d77aed0445b697425fbe59578655bd9213383의 CI 성공 후 재승인 대기, 이전 정상 고유 링크 유지 | [34947715076](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34947715076) |
| 이전 SHA 승인 거부 | 현재 전체 head SHA와 다르다는 오류로 Cloudflare 초기화 전 거부 | [34947665169](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34947665169) |
| 새 SHA 승인·정리 | 같은 pr-5 주소 갱신, 이전 asset/pointer 두 개 삭제, 총 7배포 유지, baseline 고정, WASM 42 확인 | [34947839632](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34947839632) |
| 실패 CI 우회 불가 | a542726ca182261a4dc4b95c0cce599a210ce4f7에서 build 성공·Quality 실패. 정확한 SHA를 승인해도 게시 차단, 이전 정상 링크 유지 | [34948229326](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34948229326) |

봇 comment ID 5677160680은 전체 여정에서 한 개로 유지됐다. 비교 기준은 devel 5f917413eaecab36b1ed7eded9759d64368990fb의 기존 asset을 공유했다.

## 미검증 범위와 운영 주의

- 외부 작성자가 직접 수행한 force-push, 실제 maintainer 권한 회수, 비권한 rerun, 게시 API 호출 도중 head 변경의 모든 순열은 실검증하지 않았다. 로컬 계약 테스트 및 내부 PR force-push 증거와 구분한다.
- 게시 승인은 한 workflow_dispatch 실행에만 유효하다. 동일 SHA의 자동 후속 이벤트에도 영구 승계하지 않는다.
- 이전 SHA를 입력한 조기 실패는 verification.json 생성 전 종료되어 artifact 업로드도 실패한다. 해당 부정 시험은 실행 로그로 증명한다.
- 시험 앱은 최소 WASM fixture다. rhwp Studio PR-head 빌드 이식, 전체 필수 CI gate 연결, 실제 Studio 저장·재열기는 별도 단계다.
- 기존 수동 Studio 배포와 내부 PR/devel은 보존한다. rhwp 운영 저장소의 workflow 또는 권한 설정은 바꾸지 않았다.

## 종료 결과

외부 작성자가 PR5를 닫은 뒤 [34948373374](https://github.com/postmelee/rhwp-preview-lab/actions/runs/34948373374)에서 PR5 asset/pointer 두 개를 삭제했다. 총 배포 수는 7에서 5로 복귀했다. 수동 Studio 1개, devel 앱/포인터 2개, 내부 PR3 앱/포인터 2개와 공유 baseline은 보존했다. PR5를 병합하지 않았으며 fork 저장소와 시험 브랜치는 증거로 남겼다.
