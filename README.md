# rhwp Preview Lab

[**미리보기 열기**](https://postmelee.github.io/rhwp-preview-lab/) · [업데이트 상태](https://github.com/postmelee/rhwp-preview-lab/actions/workflows/devel-pages.yml)

[rhwp](https://github.com/edwardkim/rhwp)의 개발 브랜치(`devel`)에서 빌드한 한글 문서 편집기 **rhwp Studio**를 브라우저에서 써볼 수 있는 비공식 미리보기입니다. 정식 릴리즈 전에 HWP·HWPX 문서를 열고 편집하거나, 최근 변경 사항을 확인할 때 사용할 수 있습니다.

## 사용 방법

1. 미리보기를 열고 HWP 또는 HWPX 문서의 **복사본**을 엽니다.
2. 문서 열기·편집·저장 동작을 확인합니다. 개발 빌드이므로 중요한 문서는 원본을 따로 보관하세요.
3. 문제를 제보할 때는 화면에 표시된 **소스 SHA**, 브라우저와 OS, 재현 절차를 함께 남겨 주세요. 공유가 가능한 경우에만 재현용 문서를 첨부해 주세요.

## 버전과 업데이트

- 화면에 표시된 **소스 SHA**는 현재 제공되는 rhwp 커밋입니다. 함께 표시된 시각은 빌드 시각입니다.
- GitHub Actions가 `devel` 변경을 주기적으로 확인하고, 빌드와 브라우저 기본 검증을 통과한 결과를 GitHub Pages에 게시합니다. 새 빌드에 실패하면 이전에 게시된 버전을 사용할 수 있으므로, 최신 여부는 페이지를 새로고침해 확인하세요.
- 최신 `devel`이 반영됐다는 표시는 모든 upstream 검사나 편집 기능이 검증됐다는 뜻은 아닙니다. 안정 버전은 [rhwp 정식 릴리즈](https://github.com/edwardkim/rhwp/releases)에서 확인할 수 있습니다.

## 문제 제보 및 문서

- Studio의 문서 열기·렌더링·편집 문제: [rhwp 이슈](https://github.com/edwardkim/rhwp/issues)
- 미리보기 주소·업데이트·버전 표시 문제: [Preview Lab 이슈](https://github.com/postmelee/rhwp-preview-lab/issues)
- 유지보수: [배포·복구 안내](docs/devel-preview/OPERATIONS.md) · [구현 및 검증 기록](docs/devel-preview/VALIDATION.md)
- 과거 실험: [Cloudflare PR 미리보기 기록](docs/archive/cloudflare-pr-preview.md)
