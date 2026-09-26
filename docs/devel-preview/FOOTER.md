Issue: https://github.com/postmelee/rhwp-preview-lab/issues/12

## 목적

미리보기 하단에서 한국시간, 실제 로드한 코드에 반영된 마지막 PR, 빌드 후 경과 시간을 바로 확인한다. 사용자 요청에 따라 기존 패치를 사용하지 않고 현행 코드에 구현한다.

## 범위와 수용 조건

- UTC `built_at`을 유지하고 화면만 `Asia/Seoul`의 KST 절대 시각으로 표시한다.
- 실제 source SHA 기준으로 devel에 병합된 PR 번호·링크·제목을 표시한다. 직접 커밋이면 제한된 first-parent 이력에서 가장 가까운 PR을 찾고 이후 커밋 수를 표시한다. 모호하거나 API 실패면 PR 미확인으로 표시하며 배포는 계속한다.
- `Built … ago`를 페이지 진입/30초 간격/탭 복귀 시 갱신한다. 이 표시에는 API 호출이 없고 자동 새로고침하지 않는다.
- 기존 SHA·최신 여부·Actions 링크와 24px 상태 영역을 유지한다.
- lab 코드·테스트만 변경한다. upstream rhwp 및 예약 방식은 변경하지 않는다.

## 검증

KST 날짜 경계, 고정 시각/미래 시계/잘못된 시각, PR 대상·병합 SHA·모호한 후보·조회 실패, HTML escaping, 상대 시간의 실제 스크립트 초기화·타이머·탭 복귀, PR release CI 및 공개 배너를 확인한다.

Related: #8

## 구현·로컬 검증

- `footer.py`에서 source SHA와 일치하는 merged/devel PR만 선택한다. first-parent 최대 20개 후보, 요청당 최대 3초/응답 1MiB, 전체 조회 시간 예산 20초를 둔다. 타임아웃·API 한도·응답 모호성은 `last_pr: null`로 처리한다. 공개 API를 쓰므로 새 토큰·권한이 없다.
- `site.py`는 UTC metadata를 유지하고 KST `<time datetime>` 및 HTML escape한 PR 링크/제목을 만든다. `status.js`는 고정된 시각을 즉시/30초/탭 복귀에 갱신한다. GitHub 최신 여부 조회와 별개다.
- Python 39개, JavaScript 7개 통과. actionlint(기존 cache-mode 미지원 진단만 제외), JS 구문 검사, diff whitespace 통과.
- 공개 API 실측: 배포 SHA `c80a8370ab294259557c850c2e54495ecd0e79c0`에서 PR #7432를 한 요청으로 확인했다.
- 로컬 배너 fixture를 실제 브라우저에서 확인했다. 1280×720에서 한글/KST/PR 링크/Built 표기가 24px 영역에 표시된다. fixture는 전체 Studio 실행 검증을 대체하지 않는다.
- PR CI에서는 실제 release Studio 하위 경로의 KST/원본 UTC/PR 링크·제목/source SHA/편집 영역 경계를 검사하고 기존 HWPX roundtrip을 유지한다. CI·공개 배포 결과는 이슈에 이어서 기록한다.
