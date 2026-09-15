# Studio 미리보기 — 운영 이식 후보

현재는 로컬 후보이며 rhwp 운영에 활성화하지 않았다. 실제 Linux Studio 배포·브라우저 검증은 별도 시험 저장소에서 수행했다. 최종 두 workflow의 결합 실행은 제출 전 별도 시험이 필요하다.

## 실행 경계

- `studio-preview-build.yml`: 일반 `pull_request`에서 정확한 head만 빌드한다. GitHub의 fork Actions 승인 정책을 따른다. contents read, deployment secret 없음, checkout credential 보존 없음, Actions cache 사용 없음. PR 빌드는 다른 CI와 병행한다.
- `studio-preview.yml`: 신뢰된 main의 controller를 실행한다. 해당 CI 전체와 최신 native PR build 성공 후 게시한다. 이 실행에서 빌드하는 source는 GitHub API로 확인한 devel 또는 PR base뿐이다. fork head를 `workflow_run`/`pull_request_target`/main 수동 실행에서 빌드하지 않는다.
- privileged publisher는 ZIP의 정적 바이트만 검사·업로드한다. PR의 npm hook, JS, WASM, GitHub script를 실행하지 않는다. PR artifact를 devel/비교 기준의 신뢰된 산출물로 재사용하지 않는다.
- 외부 PR은 CI 실행 승인과 별개로 `workflow_dispatch`에 PR 번호와 현재 전체 SHA를 입력해야 게시한다. 최초 실행자와 재실행자의 현재 write/maintain/admin 권한을 게시 직전에 확인한다. 새 head는 새 승인이 필요하다.

## CI·산출물 계약

`gate.cjs`는 기존 classifier/policy/evidence 모듈을 재사용한다. 정책상 비대상 skip과 실패를 구별하고, 같은 head에서 관찰된 다른 PR workflow의 실패·대기도 차단한다. housekeeping 취소 workflow만 제외한다. review-only 이전 head 증거 재사용은 아직 지원하지 않으며 증거 부족으로 차단한다.

`trusted-policy.json`의 6개 Git blob SHA는 source base의 정책·CI 정의가 알려진 계약과 같은지 검사한다. 정책 변경 시 trusted main의 snapshot을 검토·갱신해야 한다. 자동으로 새로운 정책을 신뢰하지 않는다. 실행 run/attempt, repository ID, branch, head SHA, workflow ID/path/event, artifact 이름·digest·ZIP metadata를 대조하고 게시 직전에 다시 읽는다.

빌드 recipe는 두 workflow와 prepare/recipe 코드의 digest로 구분한다. 동일 source SHA라도 recipe가 바뀌면 재사용하지 않는다. gate/build/publisher의 harness checkout은 동일 SHA로 고정한다. native PR producer와 controller의 recipe가 다르면 재빌드가 필요하다.

배포된 신뢰된 immutable asset만 재사용한다. 기존 CI의 merge-commit/dev WASM artifact는 release head 산출물과 달라 사용하지 않는다. 기본 브랜치 캐시를 오염시킬 수 있는 이벤트에서 외부 코드를 실행하지 않는다. Cargo/npm shared cache 최적화는 보류했다.

## 설정안

운영 적용 승인 후 별도 Cloudflare **Direct Upload** Pages 프로젝트를 만든다. production branch는 `devel`이어야 한다. 사용자 도메인 없이 `<project>.pages.dev`, `pr-N.<project>.pages.dev`가 제공된다. 이 코드는 프로젝트·production branch 설정을 변경하지 않는다.

| 종류 | 이름 |
| --- | --- |
| GitHub Secret | `CLOUDFLARE_PREVIEW_API_TOKEN` |
| GitHub Variable | `CLOUDFLARE_PREVIEW_ACCOUNT_ID` |
| GitHub Variable | `CLOUDFLARE_PREVIEW_PROJECT` |

main에 controller/의존 모듈/두 workflow를 준비한 뒤 devel 및 PR 경로를 검증한다. native PR build 정의도 PR base에 존재해야 한다. devel 병합만으로 main의 trusted code가 준비됐다고 간주하지 않는다. 활성화 순서와 운영 PR 제출은 별도 승인 단계다.

## 보존·비용 제한

PR별 최신 정상 pointer와 head asset, 최초 게시 당시 base asset을 보존한다. 기존 PR의 base가 이동해도 비교 기준은 고정한다. 닫힌 PR 자원은 현재 열린 PR과 공유 기준 참조를 다시 확인한 후 삭제한다. 실패 시 이전 정상 링크를 표시한다. devel pointer는 최신 정상 devel을 가리킨다.

ZIP 100 MiB, 파일 25 MiB, 파일 수 20,000, artifact 보존 3일, 한 게시 실행 신규 deployment 12개, 관리 deployment 100개가 상한이다. 상한 초과는 실패로 처리하며 무제한 과금 방지의 보증은 아니다. static-only이며 Functions/Workers 파일은 거부한다.

controller/publisher는 `queue: max`로 직렬화한다. GitHub가 허용하는 최대 대기 100개를 초과하면 실행이 취소될 수 있다. 이미 진행 중인 source가 오래되면 게시 직전 live SHA 검사로 차단한다. 새 PR head 빌드는 이전 PR 빌드를 취소한다.

## 검증·복구

```sh
python3 -m unittest discover -s scripts/preview/tests -v
node --test scripts/preview/*.test.cjs
node --test scripts/tests/ci-impact-classifier.test.cjs scripts/tests/ci-impact-policy.test.cjs scripts/tests/ci-workflow-evidence.test.cjs
```

현재 설치된 actionlint는 `queue` 구문을 모른다. 해당 단일 진단만 제외하여 나머지 구문 검사를 수행했고, GitHub 실제 3회 queue probe로 native 구문과 실행을 검증했다. 이를 최종 rhwp workflow 실행 검증으로 대체하지 않는다.

장애 시 승인된 운영자가 `studio-preview.yml`을 비활성화하면 새 게시를 중단할 수 있다. 공개 링크 삭제는 별도 Pages 정리이며 shared baseline 참조를 확인해야 한다. Secret 만료 시 이전 정상 배포는 남고 새 게시가 실패한다.

실행 전 남은 gate: 최종 native PR producer + controller 결합을 시험 저장소에서 검증, rhwp의 main/devel 차이와 관련 required check 영향 재확인, 운영 프로젝트 설정, 활성화 후 첫 PR/devel/close 시험. 이 후보의 로컬 테스트와 lab 수동 probe 성공만으로 운영 준비 완료를 선언하지 않는다.
