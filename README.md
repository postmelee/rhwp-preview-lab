# rhwp 미리보기 시험 저장소

[edwardkim/rhwp #7159](https://github.com/edwardkim/rhwp/issues/7159)의 격리 시험용이다. 실제 rhwp 운영 CI에는 연결하지 않는다.

## 현재 범위

- `Lab CI`: 정확한 PR head checkout → 합성 앱 검증 → 작은 WASM 정적 앱 artifact.
- `Lab Quality`: 별도 필수 검증. 하나라도 실패하거나 대기하면 게시하지 않는다.
- `Lab Preview`: 기본 브랜치의 코드만 실행, GitHub에서 현재 head 및 두 workflow의 최신 run/attempt 재조회, 정적 ZIP 검증, 봇 코멘트 한 개 갱신.
- devel push는 해당 SHA 산출물을 검증한다. 결과는 Actions summary와 verification artifact에 남긴다.
- 수동 실행은 최신 head의 성공 artifact를 재검증·재게시한다. 재빌드는 해당 CI를 rerun한다.
- PR 종료 이벤트는 코멘트를 종료 상태로 바꾼다. reopen은 새 CI 증거를 검증한다.

Cloudflare는 아직 연결하지 않았다. 코멘트는 호스팅 미설정을 명시하며, 실제 미리보기 URL을 만들거나 배포 성공을 주장하지 않는다. artifact는 3일 보존한다. 비용이 발생하는 서비스나 secret을 추가하지 않는다.

## 로컬 검증

```sh
python3 -m unittest discover -s tests -v
actionlint
```

`lab/case.json`은 시험 입력이다. `fail_ci`, `fail_quality`, `delay_seconds`로 실패·경쟁 상태를 재현한다. delay는 90초 이하, workflow timeout은 5분이다.

## 신뢰 경계와 미완료 항목

PR 실행은 contents:read이며 credential을 checkout에 남기지 않는다. publisher에는 contents:read/actions:read/pull-requests:write만 있다. 대기 concurrency 이벤트가 합쳐져도 요청을 놓치지 않도록 매번 열린 PR 전부와 devel을 재조정한다. 이 방식은 소규모 시험용이며 운영 규모에서는 요청별 큐 설계가 필요하다. publisher는 PR 코드·artifact를 실행하지 않고 ZIP 경로·용량·정적 파일 목록을 검사한다. CI 및 Quality workflow가 기본 브랜치와 달라진 PR은 게시를 차단한다.

정적 앱은 신뢰하지 않는 코드다. 실제 호스팅 시 운영 앱과 분리된 origin을 사용해야 한다. 최신 head 재조회와 코멘트 갱신 사이에는 GitHub 원자적 조건부 쓰기가 없으므로 표시 SHA를 명시하고 후속 이벤트로 조정한다. Cloudflare 별칭 교체·배포 정리·비교 기준 유지·fork 권한 검증은 별도 실제 실행 증거가 필요하다.

## 복구

문제가 생기면 이 시험 저장소의 `Lab Preview`만 비활성화한다:

```sh
gh workflow disable preview.yml --repo postmelee/rhwp-preview-lab
```

GitHub Pages·Cloudflare·rhwp 운영 설정에는 영향이 없다.
