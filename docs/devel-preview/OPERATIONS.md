# devel 미리보기 운영

Issue: [#8](https://github.com/postmelee/rhwp-preview-lab/issues/8). 현재 상태: 구현 PR 검증 중, Pages 미활성화.

## 사용

예상 URL은 https://postmelee.github.io/rhwp-preview-lab/ 이다. 배너의 소스 SHA와 빌드 시각이 실제 실행 버전을 나타낸다. 최신 여부는 페이지를 열었을 때 공개 GitHub API로 조회한다. API 한도/네트워크 오류면 `최신 여부 확인 불가`를 표시한다. 갱신 상태 링크는 Actions의 실행·실패 로그를 연다. 최신 devel이라는 표시는 upstream의 전체 CI 또는 모든 기능이 통과했다는 뜻이 아니다.

수동 갱신: Actions → Devel Pages → Run workflow → main. `force=false`는 즉시 변경을 조회하며 동일 버전과 실패 재시도 간격을 존중한다. `force=true`는 현재 upstream devel을 다시 빌드한다. 진행 중 빌드가 있으면 기다린다.

## 비용·사용량

- 공개 저장소의 표준 Linux GitHub-hosted runner를 쓴다. 유료 larger runner나 Cloudflare API는 사용하지 않는다.
- 예약 목표는 매시 2,7,…,57분이다. 하루 288회/30일 8,640회 조회지만 빌드와 배포는 변경 또는 재시도 시에만 한다.
- SHA가 같으면 작은 Python gate job만 실행한다. 빌드 artifact는 1일, 브라우저 검증 증적은 3일 보관한다. 캐시는 초기 버전에서 사용하지 않는다.
- 동일 SHA 실패는 한 시간 후 재시도한다. 새 SHA와 수동 force는 즉시 시도할 수 있다.
- 실제 갱신 시간은 예약 지연 + runner 대기 + release 빌드 + 배포 시간이다. GitHub schedule은 정확한 5분 SLA가 아니며, 공개 저장소에 60일 동안 활동이 없으면 비활성화될 수 있다.
- Pages 및 artifact 저장량은 GitHub 정책을 따른다. 정적 산출물은 100MiB로 제한하며, 사용자 파일은 사이트 배포물에 넣지 않는다.

## 상태와 복구

조회부터 배포 종료까지 workflow-level concurrency로 직렬화한다. 대기 실행은 합쳐지고 잠금 취득 후 최신 SHA를 고른다. 오래된 workflow revision의 rerun은 gate/publish guard에서 차단한다. 빌드 중 새로운 upstream 커밋이 들어와도 이미 시작한 빌드를 계속하며 다음 조회에서 최신 커밋을 처리한다.

`devel-preview-build` deployment environment의 payload가 재시도 상태다. 이 저장소의 harness ref, upstream SHA, recipe, run/attempt를 기록한다. 마지막 성공 배포 여부는 공개 `build.json`과 함께 확인한다. GitHub API 오류는 무조건 재빌드를 시작하지 않고 조회 실패로 종료한다. 비정상 종료로 finish가 실행되지 않아도 1시간 후 미완료 기록을 재시도할 수 있다.

빌드나 브라우저 검증 실패는 publish를 실행하지 않으므로 기존 사이트를 보존한다. Pages 게시 후 공개 metadata 검증 실패는 로그에서 실제 게시 상태를 확인한다. 이미 게시된 사이트를 자동 롤백하지는 않는다. 성공은 공개 metadata의 SHA/recipe/run/attempt까지 일치했을 때 기록한다.

일시 중단:

```sh
gh workflow disable devel-pages.yml -R postmelee/rhwp-preview-lab
```

기존 사이트는 유지된다. 다시 활성화 후 수동 실행으로 복구한다. 이전 Cloudflare 실험 workflow/배포/Secret은 별개로 보존되어 있으므로 신규 서비스 중단이 이를 정리하지 않는다.

## 최초 활성화

1. 구현 PR의 계약 테스트, 실제 release 빌드, Pages 하위 경로 브라우저 검증을 확인한다.
2. 저장소 Settings → Pages → Source를 GitHub Actions로 설정한다.
3. `github-pages` environment는 main만 배포하도록 설정한다.
4. 검증된 PR을 main에 통합한다. 변경된 workflow/script의 main push가 첫 빌드를 시작한다.
5. 실제 공개 URL/metadata/브라우저를 확인하고, 수동 no-force 실행이 같은 SHA를 생략하는지 확인한다. 예약 실행은 별도로 관찰한다.

새 토큰은 필요 없다. 저장소 GITHUB_TOKEN의 job별 최소 권한과 Pages OIDC를 사용한다. build job에는 게시 권한이나 Secret이 없다. PR 검증에는 배포를 허용하지 않는다.

## 로컬 검증

```sh
python3 -m unittest discover -s devel/tests -v
actionlint -ignore 'unexpected key "cache-mode" for "workflow" section' .github/workflows/devel-pages.yml
node --check devel/smoke.mjs
```

설치된 actionlint는 최신 GitHub `cache-mode` 문법을 아직 모르므로 그 진단만 제외한다. GitHub가 실제 workflow를 받아 실행하는지 PR CI에서 확인한다.
