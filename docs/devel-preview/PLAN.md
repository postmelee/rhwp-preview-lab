# devel 전용 미리보기 계획

- Issue: https://github.com/postmelee/rhwp-preview-lab/issues/8
- Date: 2026-09-17
- Baseline: lab main ed1447466498cc7807b25b1e0af4c56b00cb78b4
- Status: implementation pending

## 목적과 경계

edwardkim/rhwp의 devel을 읽어 이 저장소의 GitHub-hosted runner에서 release Studio를 만들고 GitHub Pages에 게시한다. upstream 저장소는 변경하지 않는다. 기존 Cloudflare 실험과 기록은 보존한다. 신규 워크플로는 PR 미리보기나 봇 코멘트를 만들지 않는다.

## 설계

1. `Devel Pages`는 매시 2,7,12,…,57분에 실행한다. schedule은 지연/누락 가능하고 공개 저장소 60일 활동 부재 시 비활성화될 수 있다. 수동 실행으로 즉시 조회 또는 강제 재빌드를 제공한다.
2. workflow 전체를 같은 concurrency group에서 직렬화하고 진행 중 실행을 취소하지 않는다. 기본 대기 슬롯 하나를 통해 밀린 요청을 합친다. 잠금을 얻은 뒤 devel SHA를 읽어 오래된 예약 시점의 SHA를 빌드하지 않는다.
3. gate는 Python 표준 라이브러리로 SHA, 현재 공개 build.json, 이 저장소의 전용 deployment environment 기록을 조회한다. 동일 SHA와 빌드 레시피면 생략한다. 조회 오류는 변경 없음으로 숨기거나 무조건 재빌드하지 않고 실패한다.
4. 변경 시 GitHub deployment payload에 upstream SHA/recipe/run을 기록한다. 실패·중단은 1시간 재시도 간격을 적용한다. 완료 상태를 못 남긴 pending 기록도 1시간 lease 후 복구한다. 수동 force는 이 간격과 동일 SHA 생략을 우회한다. 5분 poll마다 Git 커밋이나 artifact를 만들지 않는다.
5. 읽기 권한의 별도 build job에서 upstream 정확한 SHA를 checkout한다. credential을 남기지 않으며 Pages/OIDC/Cloudflare Secret을 전달하지 않는다. cache-mode none, Node 자동 cache 비활성화, 초기 버전은 캐시 없음. 기존 검증 toolchain(Node 24.15.0, Rust 1.93.1, wasm-pack 0.15.0)을 사용한다.
6. 기존 preview prepare의 sample 제외와 폰트 복사 방식을 참고한 독립 Pages adapter를 만든다. Vite base는 `/rhwp-preview-lab/`. PWA와 불필요한 OCX 플러그인은 끈다. 엔진 소스의 임의 문자열 치환 없이 공식 Vite base 경로를 우선하며 실제 브라우저 요청으로 확인한다.
7. 빌드 job에서 파일 수/크기/심볼릭 링크/정적 파일/provenance를 검증하고 Pages artifact를 업로드한다(1일 보관). publish job은 upstream 코드를 실행하지 않고 검증된 artifact만 게시한다. 게시 직전 lab main과 workflow SHA를 비교하여 오래된 harness rerun을 막는다.
8. 실패 시 이전 정상 Pages 배포를 유지한다. 페이지 배너에는 실제 source SHA, 빌드 시각, upstream 및 Actions 상태 링크를 넣는다. 최신 upstream SHA 조회 실패는 최신이라고 단정하지 않는다. 매 poll을 위해 전체 정적 사이트를 재배포하지 않는다.
9. main만 게시 가능하다. PR에서는 읽기 권한의 테스트 및 실제 최신 devel 빌드를 수행하여 경로/산출물을 검증한다. Pages 설정과 운영 활성화는 검증된 PR을 기준으로 진행한다.

## 자원과 실패 정책

- no-change: 작은 gate job 하나. source checkout, npm, Rust 설치, artifact, 배포 없음.
- change: gate ≤ 5분, build ≤ 30분, deploy ≤ 10분, finish ≤ 5분.
- 동시에 실제 빌드 하나. 초기 캐시 없음; 먼저 실측 후 필요하면 별도 개선한다.
- 사이트 100MiB / 파일 20,000개 / 개별 파일 50MiB 상한. GitHub Pages 서비스 상한보다 낮게 설정한다.
- GitHub deployment 기록은 변경/재시도 시만 생성. 기존 실패 기록은 진단 근거로 보존한다.
- 실제 build 실패는 devel 기능 결함과 harness 호환성 문제를 구분해 Actions 로그로 조사한다. upstream CI 전체 통과를 대체하는 페이지가 아니다.

## 검증 순서

1. 로컬 계약: unchanged, recipe 변경, 새 SHA, 실패 backoff, pending 복구, force, 비정상 API 응답, unsafe artifact/provenance.
2. 워크플로 권한/trigger/concurrency 검사 및 actionlint.
3. PR의 실제 Linux release 빌드 + artifact 검증. 로컬 Pages 하위 경로에서 Studio 열기, 문서 열기, 저장·재열기 및 폰트/CanvasKit 요청 확인.
4. GitHub Pages 설정 및 main 통합 후 실제 공개 URL 검증, 동일 SHA 생략, 예약 trigger 관찰. 실제 검증하지 못한 실패/경쟁 경계는 계약 테스트와 구분한다.
5. 최종 head·source SHA·run·URL·제약을 보고서에 기록한다.

## 공식 근거

- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#concurrency
- https://docs.github.com/en/rest/deployments/deployments
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
