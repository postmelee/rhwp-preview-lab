# devel Pages 검증 보고

Issue: https://github.com/postmelee/rhwp-preview-lab/issues/8

## 범위

upstream `edwardkim/rhwp` devel을 독립 lab에서 읽고 release Studio를 GitHub Pages에 게시한다. rhwp 소스/CI/Secret 변경은 없다. 기존 Cloudflare 실험은 보존했다.

## 구현과 검증 이력

- 계획 커밋 `c1dfd84`: 변경 감지·직렬화·재시도 상태·Pages 경로·권한 분리를 기록했다.
- 구현 PR [#9](https://github.com/postmelee/rhwp-preview-lab/pull/9), 최종 코드 `f7531c1d5de52d8f66b750d504de46b20ee211bb`, main merge `58af12692da88e8270819856db95aa6fc2370e25`.
- 첫 CI [35225553978](https://github.com/postmelee/rhwp-preview-lab/actions/runs/35225553978): release 빌드 성공, 브라우저 테스트가 DEV 전용 객체를 기다려 실패. 제품 회귀로 판정하지 않았으며 공개 명령 API/파일 UI를 쓰도록 테스트를 수정했다.
- 수정 후 CI [35227065584](https://github.com/postmelee/rhwp-preview-lab/actions/runs/35227065584): 계약 26개 + 실제 release + 정적 검증 + CanvasKit/폰트/WASM + HWPX 저장·재열기 통과.
- 첫 운영 [35228335603](https://github.com/postmelee/rhwp-preview-lab/actions/runs/35228335603): gate/build/publish/finish 모두 성공. 공개 metadata의 SHA/recipe/run/attempt 일치를 확인했다.
- 직렬 대기와 unchanged [35229532557](https://github.com/postmelee/rhwp-preview-lab/actions/runs/35229532557): 첫 운영 빌드 중 요청한 수동 실행이 대기 후 `already published. Build: False`로 종료했다.
- 첫 운영의 Pages artifact는 finalizer가 삭제했고 `devel-evidence-1` 65,716바이트만 남았다. deployment `6503976045`의 최종 상태는 success다.
- Mac 직접 시각 확인에서 기존 배너가 확대·축소를 가리는 것을 발견해 [#10](https://github.com/postmelee/rhwp-preview-lab/pull/10)으로 상태 표시줄 24px를 분리했다. 로컬 정적 산출물에서 앱 하단/배너 상단 모두 y=696임을 확인했다. 최종 코드 `f944a77f2820c928408288fa3c54a33e5c647436`의 [CI 35228955360](https://github.com/postmelee/rhwp-preview-lab/actions/runs/35228955360)도 통과했다(CI viewport에서 양쪽 경계 y=976). main merge는 `ad09b9c827cd3f48358ec199f7caa1d8b2ec6c3b`다.

## 실제 확인한 문서 여정

CI의 production 앱을 `/rhwp-preview-lab/?renderer=canvaskit`에서 연 뒤 `devel Pages HWPX roundtrip`을 키보드로 입력했다. 공개 저장 명령이 쓴 HWPX 7,364바이트의 section XML에서 문장을 확인했다. 그 파일을 파일 입력 경로로 다시 열고, 다시 저장한 7,364바이트의 XML에도 문장이 유지되었다. Chrome의 저장 파일 선택 경계는 테스트용 sink를 사용했다. 실제 OS 저장 대화상자 자체의 조작을 자동화한 검사는 아니다.

Mac in-app Browser에서는 기본 Canvas2D 화면의 한글 메뉴, 문서 입력과 배너를 직접 확인했다. Linux CI 스크린샷의 한글 UI는 네모로 보여 그 캡처만으로 UI 정상 판정을 하지 않았다. Mac 브라우저에서는 한글 메뉴가 정상으로 표시되는 것을 직접 확인했다. 이는 한컴 출력 정합성이나 모든 편집 기능의 검증을 뜻하지 않는다.

## 자원 실측과 제한

첫 코드 실행 기준 upstream checkout 104초, 도구 설치 80초, source build 449초. 정적 파일은 59개/45,241,590바이트였다. 이는 측정한 한 실행이며 예약/runner 대기나 후속 devel 변경에 따라 달라진다.

동일 SHA와 동일 recipe는 작은 gate만 실행한다. 최초 버전은 캐시를 만들지 않는다. 운영 Pages artifact는 처리 후 삭제하고, 정리 실패/PR artifact는 1일 만료, 증적은 3일 보존한다. 기존 실험 artifact까지 삭제하는 정책은 아니다.

배포 source SHA는 `236a601da803b53429e9090eef652c661dd3bfe2`. 이후 devel 변경 시 달라지므로 현재 버전은 공개 build.json과 배너로 확인한다.

## 계약 테스트와 실검증 구분

실제 검증: 정확한 SHA build, 공개 Pages 게시, CDN metadata 일치, 직렬 대기 후 동일 SHA 생략, 운영 artifact 삭제, release 문서 저장·재열기.

계약/구조 검증: 1시간 실패 재시도, 중단 lease 복구, force 우회, API 오류 시 새 빌드 금지, 오래된 harness 게시 차단, unsafe/과대 파일·다른 provenance 차단, 실패 build에서 publish 미실행. upstream의 실제 실패 커밋을 주입하거나 모든 경쟁 순열을 재현한 검사는 아니다.

예약 cron은 `2-59/5 * * * *`(UTC)이다. GitHub의 지연/누락 가능성과 60일 비활성화 조건은 운영 안내를 따른다.

## 보존한 증적

- [PR #10 브라우저 결과](evidence/pr-10-browser.json)
- [PR #10 정적 산출물 검사](evidence/pr-10-static.json)
- [Mac 배너 경계 직접 확인](evidence/mac-local-layout.png)

## 최종 공개 운영 확인

- 공개 URL: https://postmelee.github.io/rhwp-preview-lab/
- 최종 배포 [35230254557](https://github.com/postmelee/rhwp-preview-lab/actions/runs/35230254557): source SHA는 유지되고 recipe가 `67291c44ca423de74d49f23bc7fd14a8047be2cea55036f08fe1bd90863783f6`으로 바뀌어 자동 재빌드·게시되었다. gate/build/publish/finish 모두 success.
- 공개 metadata: [public-build.json](evidence/public-build.json), built_at `2026-09-17T14:06:10.693378+00:00`.
- 최종 unchanged [35231522382](https://github.com/postmelee/rhwp-preview-lab/actions/runs/35231522382): gate 5초, build/publish/finish 모두 skipped, `already published. Build: False`.
- 최종 운영 Pages artifact 삭제 후 `devel-evidence-1` 67,610바이트만 남음을 API로 확인했다.
- 공개 앱의 기본 Canvas2D 화면에 `Public devel preview verified`를 입력했다. 한글 UI, 최신 devel 표시, 앱 하단/배너 상단 y=696을 직접 확인했다. [공개 화면](evidence/public-studio.png).
- 예약 전제: default branch main, non-fork/public/활성 저장소, workflow active, main에 5분 cron 존재를 확인했다. **2026-09-17 14:08 UTC까지 실제 schedule 이벤트는 미관찰**이다. 수동/직렬 대기/중복 생략을 검증했지만 최초 예약 trigger 확인은 별도로 남긴다. 이 확인 전에는 #8을 완료로 닫지 않는다.
