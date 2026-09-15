# rhwp 미리보기 시험 저장소

[edwardkim/rhwp #7159](https://github.com/edwardkim/rhwp/issues/7159)의 격리 시험용이다. 실제 rhwp 운영 CI에는 연결하지 않는다.

## 현재 범위

- `Lab CI`: 정확한 PR head checkout → 합성 앱 검증 → 작은 WASM 정적 앱 artifact.
- `Lab Quality`: 별도 필수 검증. 하나라도 실패하거나 대기하면 게시하지 않는다.
- `Lab Preview`: 기본 브랜치의 코드만 실행, GitHub에서 현재 head 및 두 workflow의 최신 run/attempt 재조회, 정적 ZIP 검증, 봇 코멘트 한 개 갱신.
- devel push는 해당 SHA 산출물을 검증하고 [상설 시험 앱](https://rhwp-preview-lab.pages.dev)을 갱신한다. 결과는 Actions summary와 verification artifact에 남긴다.
- 수동 실행은 최신 head의 성공 artifact를 재검증·재게시한다. 재빌드는 해당 CI를 rerun한다.
- PR 종료 이벤트는 코멘트를 종료 상태로 바꾼다. reopen은 새 CI 증거를 검증한다.

Cloudflare Pages Direct Upload에 연결했다. PR 코멘트는 head 고정 주소·고유 버전·고정 baseline·현재 devel 링크를 제공한다. 새 배포 검증 후 참조 없는 관리 배포를 삭제한다. artifact는 3일 보존한다. 설치 단계와 PR 빌드는 토큰을 받지 않으며 trusted publisher만 GitHub Secret을 사용한다. Functions·유료 플랜·R2는 도입하지 않는다.

## 로컬 검증

```sh
python3 -m unittest discover -s tests -v
actionlint
```

`lab/case.json`은 시험 입력이다. `fail_ci`, `fail_quality`, `delay_seconds`로 실패·경쟁 상태를 재현한다. delay는 90초 이하, CI timeout은 5분, publisher는 15분이다.

## 신뢰 경계와 미완료 항목

PR 실행은 contents:read이며 credential을 checkout에 남기지 않는다. publisher에는 contents:read/actions:read/pull-requests:write만 있다. 대기 concurrency 이벤트가 합쳐져도 요청을 놓치지 않도록 매번 열린 PR 전부와 devel을 재조정한다. 이 방식은 소규모 시험용이며 운영 규모에서는 요청별 큐 설계가 필요하다. publisher는 PR 코드·artifact를 실행하지 않고 ZIP 경로·용량·정적 파일 목록을 검사한다. CI 및 Quality workflow가 기본 브랜치와 달라진 PR은 게시를 차단한다.

정적 앱은 신뢰하지 않는 코드다. 실제 호스팅 시 운영 앱과 분리된 origin을 사용해야 한다. 최신 head 재조회와 코멘트 갱신 사이에는 GitHub 원자적 조건부 쓰기가 없으므로 표시 SHA를 명시하고 후속 이벤트로 조정한다. Cloudflare 별칭 갱신·배포 삭제·baseline 보존을 실제 검증했다. fork 권한, rhwp 운영 gate 이식, API 쓰기 도중 head 변경의 모든 순열은 아직 검증 완료 범위가 아니다.

## 복구

문제가 생기면 이 시험 저장소의 `Lab Preview`만 비활성화한다:

```sh
gh workflow disable preview.yml --repo postmelee/rhwp-preview-lab
```

자동 갱신만 중지하며 기존 Cloudflare 배포는 남는다. rhwp 운영 CI에는 영향이 없다.

## 실제 rhwp release probe

`Rhwp Release Probe`는 rhwp 고정 SHA `769582fc856f162e57604b318d41414d7b026345`를 Linux runner에서 최적화 빌드한다. PWA와 public sample corpus를 제외하고 같은 ZIP 검사 함수를 별도 읽기 전용 job에서 실행한다. PR gate 실험과 제품 build 실험을 구분한다. 해당 release artifact는 최초 수동 Pages 배포로 검증했으며 [Studio 고유 URL](https://882d9256.rhwp-preview-lab.pages.dev)에 보존한다. 자동 PR/devel 실험은 최소 WASM 앱이며 실제 rhwp 제품으로 이식하기 전이다.

설정·동작·제한: [Cloudflare 운영 상태](CLOUDFLARE_NEXT.md).
