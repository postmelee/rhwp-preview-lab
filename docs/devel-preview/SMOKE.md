# 브라우저 smoke의 문서 재열기 회귀 검증

검증일: 2026-11-11. Harness base: `e20fa8bb2f1d28e2843d7d1c9a8da93ed7e22894`.

## 확인한 문제

- [실패 실행 #316](https://github.com/postmelee/rhwp-preview-lab/actions/runs/42861394262)은 upstream `5ea1227505978156082121f1601cb03044a0583f`의 release 빌드를 완료했으나 두 번째 저장에서 30초 timeout으로 실패했다. 증적에는 로딩 50% 상태에서 Save As와 로컬 글꼴 모달이 함께 남았다.
- [성공 실행 #317](https://github.com/postmelee/rhwp-preview-lab/actions/runs/42913306767)은 실제 build/smoke/publish가 성공했다. 그러나 `result.json`의 `passed=true`와 동시에 최종 화면에 로컬 글꼴 모달이 남았고, 원본·두 번째 HWPX는 각각 7,399바이트였다. 문서 초기화·재편집 가능 여부를 검증하지 못하는 false green이다.
- [실행 #318](https://github.com/postmelee/rhwp-preview-lab/actions/runs/42942617559)은 build/publish가 생략된 gate-only 성공이다. 실제 smoke 성공과 구분한다.

문서 제목은 파싱 직후 바뀌지만 글꼴 선택·캔버스·편집기 초기화는 아직 진행 중일 수 있다. 기존의 전역 입력/기본 버튼 selector도 서로 다른 대화상자를 가리킬 수 있었다.

## 수정한 계약

1. 한국어 로케일을 고정하고, 알려진 글꼴 모달의 `대체 글꼴로 보기`만 선택한다. 감지 버튼이나 임의 모달은 누르지 않는다.
2. 제목·최종 상태 표시줄의 파일 이름, 문서 존재, 깨끗한 문서/초기 undo 상태, 캔버스, `rhwp-busy` 해제, 모달 부재를 함께 기다린다.
3. 맨 위의 Save As 대화상자를 식별하고 그 내부의 파일 이름 입력/확인 버튼만 사용한다. 저장 sink의 close, 문서 clean 전환과 모달 종료까지 기다린다.
4. 재열기 후 두 번째 문자열을 실제 키보드로 입력한다. 두 번째 HWPX의 section XML에 원본 문자열과 새 문자열이 모두 있어야 통과한다. 마지막 화면에 모달이 남아도 실패한다.

## 로컬 검증

Node 24.15.0, macOS의 headless Chrome, Puppeteer를 사용했다. 개발 서버나 개발 전용 전역은 쓰지 않았다.

#317의 공개 release에서 smoke에 필요한 정적 파일을 내려받아 실제 `/rhwp-preview-lab/` 하위 경로로 로컬 제공했다. `build.json` 전체를 실행 증적과 대조했고, `index.html` SHA-256도 metadata와 일치했다.

- Source SHA: `e118de8abadd2dffb2798036b9ffd381b96ed7d5`.
- Index SHA-256: `fe34a680cf255a722390d002a4c6447a7dc214d1def58d8f837062079189e223`.
- 수정 전: 같은 release에서 `passed=true`이면서 글꼴 모달이 남는 현상 재현. 첫 저장과 재저장 모두 7,399바이트.
- 수정 후: 독립 브라우저로 3회 반복 통과. 각 실행에서 글꼴 모달의 대체 경로를 한 번 처리하고, 재열기 후 편집·저장 검증 통과. 첫 저장 7,399바이트, 두 번째 저장 7,412바이트. 두 문자열의 XML 존재와 화면 표시를 확인했고 모달·브라우저 예외·로컬 요청 실패가 남지 않았다.
- Python: `devel/tests` 55개, `tests` 27개 통과.
- Node: 기존 상태 표시 테스트 7개, 신규 실제 브라우저 회귀 테스트 9개 통과.
- 변경 workflow actionlint (`cache-mode` 미지원 진단만 제외), JavaScript syntax, `git diff --check` 통과.
- 저장소 전체 actionlint는 변경하지 않은 `queue-probe.yml`, `studio-preview.yml`의 기존 `concurrency.queue` 구문에서 3개 진단을 냈다. 해당 workflow는 이 수정 범위에 포함하지 않았다.

신규 회귀 테스트는 늦게 뜨는 글꼴 모달, 준비 상태 이후 busy 해제, 알 수 없는 모달, 오래된 상태/undo/dirty, 두 모달의 순서, 숨은 이전 대화상자, 두 번째 문자열 누락을 검사한다. CI에서는 의존성 설치 후 실제 release smoke 직전에 실행한다.

이 변경은 smoke harness만 수정한다. 이번 로컬 검증은 이미 게시된 release의 실제 번들을 사용했으며 Rust/WASM을 새로 빌드한 검증은 아니다. 새 harness의 GitHub Actions 실행 및 운영 배포는 별도로 확인해야 한다.
