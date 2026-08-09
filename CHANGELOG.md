# DesktopOverlay 변경 내역

## [v0.3.16](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.16)

- 클릭 통과 기본값을 꺼짐으로 바꿔 최초 실행 후 바로 오버레이를 드래그해 위치를 조절할 수 있게 했습니다.
- README와 요구사항 문서의 클릭 통과 기본 동작 설명을 실제 동작에 맞춰 갱신했습니다.

## [v0.3.15](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.15)

- 소스 실행/빌드 배치의 Python 탐지 프로브가 실행 파일 경로를 출력하기 전에 종료되던 회귀를 수정했습니다.
- `.venv-runtime`, `.venv-build`가 손상된 경우 자동으로 삭제 후 재생성하도록 보강했습니다.
- 경로에 닫는 괄호가 포함되어도 배치 파일의 가상환경 생성 안내가 깨지지 않도록 정리했습니다.
- 릴리스 자산이 이미 있는 부분 실패 상태에서도 릴리스 노트는 갱신하고, zip 자산 덮어쓰기만 차단하도록 publish job을 개선했습니다.
- 클릭 통과 Win32 확장 스타일 적용부에 `ctypes` 함수 시그니처와 예외 처리를 추가했습니다.
- `pip --require-hashes`가 잘못된 해시를 실제로 거부하는지 확인하는 negative CI 테스트를 추가했습니다.

## [v0.3.14](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.14)

- `v0.3.13` 릴리스 게시 실패 원인이던 Windows `pytest` 전이 의존성 `colorama`를 해시 lock에 명시했습니다.
- `v0.3.12`, `v0.3.13`에서 준비한 이슈 #61~#67 수정 내용을 실제 배포본으로 통합했습니다.
- 클릭 통과가 켜져도 아래 창 버튼이 눌리지 않을 수 있어, `WM_NCHITTEST` fallback과 함께 Win32 `WS_EX_TRANSPARENT` 확장 스타일을 적용하도록 보강했습니다.

## v0.3.13 - 릴리스 게시 실패 태그

- Git 태그는 남아 있지만 GitHub Release와 배포 파일은 생성되지 않았습니다.
- Windows CI에서 `pytest`의 Windows 전용 전이 의존성 `colorama`가 해시 lock에 없어 설치 단계가 실패했습니다.
- 실제 배포는 `v0.3.14`에 통합됐습니다.

- `v0.3.12` 릴리스 게시 실패 원인이던 Windows 전용 PyInstaller 의존성 `pefile`, `pywin32-ctypes`를 해시 lock에 명시했습니다.
- `v0.3.12`의 이슈 #61~#66 수정 내용을 실제 배포본으로 통합했습니다.
- 클릭 통과가 켜져도 아래 창 버튼이 눌리지 않을 수 있어, `WM_NCHITTEST` fallback과 함께 Win32 `WS_EX_TRANSPARENT` 확장 스타일을 적용하도록 보강했습니다.

## v0.3.12 - 릴리스 게시 실패 태그

- Git 태그는 남아 있지만 GitHub Release와 배포 파일은 생성되지 않았습니다.
- Windows CI에서 PyInstaller의 Windows 전용 전이 의존성 `pefile`이 해시 lock에 없어 설치 단계가 실패했습니다.
- 실제 배포는 `v0.3.14`에 통합됐습니다.

- `v0.3.8`, `v0.3.9` 실패 태그가 실제 릴리스 링크처럼 보이지 않도록 README와 CHANGELOG 표기를 정리했습니다.
- 소스 실행 문서의 Python 요구사항을 실제 의존성/CI 기준인 Python 3.10 이상으로 정정했습니다.
- 소스 실행 배치와 빌드 배치가 전역 Python 환경 대신 `.venv-runtime`, `.venv-build` 가상환경을 사용하도록 분리했습니다.
- 이미지 읽기/처리 실패 시 트레이 tooltip이 `이미지 처리 중...` 상태에 남지 않도록 실패 종류별 안내 문구로 갱신합니다.
- 릴리스 publish job이 기존 `DisplayOverlay.zip` 자산을 덮어쓰지 않고, 자산이 이미 있으면 실패하도록 변경했습니다.
- 런타임/릴리스 의존성 lock에 SHA256 해시를 추가하고 모든 설치 경로가 `--require-hashes`를 사용하도록 보강했습니다.

## [v0.3.11](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.11)

- Windows 자동 실행 바로가기 처리에서 PowerShell 실행을 신뢰 가능한 절대 경로로만 제한했습니다.
- System32 PowerShell 실행이 실패해도 `powershell.exe`/`powershell` PATH 검색으로 fallback하지 않도록 막았습니다.
- #58 보안 하드닝 회귀 테스트를 추가했습니다.

## [v0.3.10](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.10)

- Release workflow 게시 job이 checkout 없이도 저장소를 정확히 지정하도록 `gh release` 명령에 repository를 명시했습니다.
- 릴리스 게시에 실패했던 `v0.3.8`, `v0.3.9` 태그의 이슈 #54~#60 수정 내용과 workflow 보강을 실제 배포본으로 통합했습니다.

## v0.3.9 - 릴리스 게시 실패 태그

- Git 태그는 남아 있지만 GitHub Release와 배포 파일은 생성되지 않았습니다.
- `v0.3.8` 릴리스 워크플로의 게시 단계가 다운로드된 artifact 내부 경로를 고정 가정하지 않도록 보강했습니다.
- 게시 job이 실제 `DisplayOverlay.zip`과 `release_notes.md` 위치를 찾아 릴리스를 생성/갱신하도록 수정했습니다.
- `v0.3.8`의 이슈 #54~#60 수정 내용은 그대로 포함합니다.
- 실제 배포는 `v0.3.10`에 통합됐습니다.

## v0.3.8 - 릴리스 게시 실패 태그

- Git 태그는 남아 있지만 GitHub Release와 배포 파일은 생성되지 않았습니다.
- 소스 실행용 `requirements.txt`도 CI/릴리스에서 검증한 런타임 버전으로 고정했습니다.
- 초장문 GIF가 저장 프레임 제한을 우회해 원본 프레임을 끝까지 디코딩하지 않도록 원본 프레임 수 상한을 추가했습니다.
- 파일 없음, 이미지 정책 초과, 디코딩 실패를 구분해 대형/손상 이미지를 파일 없음으로 오진하지 않게 했습니다.
- 시작프로그램 바로가기의 대상 경로를 비동기 확인해 현재 실행 파일과 다르면 경로 갱신 필요 상태를 표시합니다.
- 자동 실행 바로가기 생성/검증 시 PowerShell을 SystemRoot 절대 경로로 먼저 실행하도록 하드닝했습니다.
- 사용하지 않는 `requirements-build.txt`를 제거했습니다.
- Release workflow를 read-only 빌드 job과 `contents: write` 게시 job으로 분리했습니다.
- 실제 배포는 `v0.3.10`에 통합됐습니다.

## [v0.3.7](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.7)

- 배포 압축 파일명을 `DisplayOverlay.zip`으로 변경했습니다.
- Windows x64 전용 배포라 파일명에서 플랫폼 접미사를 제거했습니다.
- 내부 실행 파일명 `Desktop_Overlay_Start.exe`는 그대로 유지합니다.

## [v0.3.6](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.6)

- 이미지가 없는 최초 실행 때 사용자가 프로그램 실행 여부를 알 수 있도록 주 모니터 중앙에 안내창을 띄웁니다.
- 안내창에서 바로 **이미지 열기** 를 선택할 수 있습니다.
- 최초 안내창은 한 번만 표시되며, 이후에는 기존 트레이 알림 흐름을 유지합니다.

## [v0.3.5](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.5)

- 네트워크 공유 경로 이미지를 저장 경로 또는 실행 인자로 사용할 때 UI 스레드에서 `exists` 검사를 하지 않도록 통일했습니다.
- 실행 인자 경로가 없고 저장된 네트워크 이미지가 있을 때 저장된 이미지를 정상 복원하도록 수정했습니다.
- 이미지 열기 실패 시 실패한 새 경로를 `config.json`에 먼저 저장하지 않고 기존 정상 경로를 유지합니다.
- **배경색 자동 추출/다시 잡기** 메뉴가 수동 배경색 지정 후에도 자동 추출 모드로 돌아가게 했습니다.
- `Win+D`, `Win+L`, `Win+Tab`, `Alt+Esc`, `Alt+Shift+Tab` 같은 Windows 예약 조합은 입력 시점에 안내하고 거부합니다.
- 자동 실행 적용 직후 종료해도 오래 기다리지 않도록 종료 대기 시간을 줄이고, 아직 끝나지 않은 worker는 안전하게 분리합니다.
- 정적 이미지 원본 상한을 80MP로 조정하고 초과 시 사용자가 취할 조치를 안내합니다.
- CI와 로컬 빌드가 릴리스 잠금 파일 `requirements-release.txt`를 공통으로 쓰도록 맞췄습니다.
- Defender 오탐 가능성을 낮추기 위해 릴리스 배포물을 PyInstaller onefile exe에서 onedir zip으로 변경했습니다.
- 회귀 테스트를 보강해 네트워크 경로, 예약 단축키, 이미지 경로 보존, 자동 배경 복귀, 픽셀 상한, startup worker 상태 전이를 확인합니다.

## [v0.3.4](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.4)

- 단축키 설정창의 캡처 UI도 `config.json` 정규화와 같은 예약 조합 판정을 사용합니다.
- `Ctrl+Tab`, `Ctrl+Shift+Tab`을 설정창에서도 등록할 수 있게 했습니다.
- `Alt+Tab`, `Ctrl+Esc`, `Ctrl+Shift+Esc`는 설정창에서도 계속 거부합니다.
- 수식어 없는 `Esc`의 캡처 취소 동작은 유지했습니다.
- 캡처 UI 전용 회귀 테스트를 추가했습니다.

## [v0.3.3](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.3)

- 단독 `Esc`, `Tab`, `Backspace`, `Delete`는 계속 거부하되 수식어가 붙은 정상 조합은 허용합니다.
- `Ctrl+Delete`, `Ctrl+Backspace`, `Ctrl+Tab`, `Ctrl+Shift+Delete` 같은 조합을 등록할 수 있게 했습니다.
- `Ctrl+Alt+Delete`, `Alt+Tab`, `Ctrl+Esc`, `Ctrl+Shift+Esc` 같은 Windows 예약 조합은 계속 거부합니다.
- 단축키 캡처 UI에서 `Backspace`/`Delete` 삭제 동작은 수식어 없는 입력에만 적용합니다.
- 예약/허용 단축키 조합에 대한 회귀 테스트를 추가했습니다.

## [v0.3.2](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.2)

- `config.json`에 직접 입력된 전역 단축키도 설정창과 같은 안전 규칙으로 검증합니다.
- `Space`, `Enter`, `F1` 같은 수식어 없는 단독키는 시작 시 제거하고, `Num0`~`Num9` 단독키만 유지합니다.
- 문자열 bool 값 `true/false`, `yes/no`, `on/off`, `1/0`을 명시적으로 해석합니다.
- 프리릴리스 태그를 자동 업데이트 대상으로 안내하지 않도록 업데이트 판정을 보강했습니다.
- 설정 파일 직접 편집 경로에 대한 회귀 테스트를 추가했습니다.

## [v0.3.1](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.1)

- 손상된 `config.json` 값을 안전하게 보정하고, 잘못된 설정은 트레이 알림으로 안내합니다.
- 설정 저장을 임시 파일 작성 후 원자 교체 방식으로 바꾸고, 휠 크기 조절 중 중복 저장을 줄이도록 지연 저장을 적용했습니다.
- 이미지 처리 worker 취소와 종료 정리를 추가해 대형 GIF 처리 중 스레드와 메모리가 누적되는 문제를 줄였습니다.
- 업데이트 확인의 예외 처리와 버전 비교를 보강해 프리릴리스/잘못된 태그를 정식 업데이트로 오진하지 않게 했습니다.
- 자동 실행 메뉴에서 동기 PowerShell 조회를 제거하고, 경로 갱신을 명시 메뉴로 분리했습니다.
- 전역 단축키 정책을 강화해 수식어 없는 단독키는 막고 `Num0`~`Num9` 단독키만 예외로 허용합니다.
- CI를 Ubuntu/Windows matrix로 확장했습니다.

## [v0.3.0](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.0)

- 트레이 메뉴에 **윈도우 시작 시 자동 실행** 체크 항목을 추가했습니다.
- 레지스트리를 쓰지 않고 Windows 시작프로그램 폴더의 `DesktopOverlay.lnk` 바로가기를 생성/삭제합니다.
- 프로그램 파일이나 폴더를 옮긴 뒤 **자동 실행 경로 갱신** 메뉴로 현재 실행 위치를 다시 등록할 수 있게 했습니다.
- README에 자동 실행 동작 방식과 최신 다운로드 SHA256을 반영했습니다.

## [v0.2.3](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.2.3)

- 단축키 설정창을 크게 조정해 주요 항목을 스크롤 없이 볼 수 있게 했습니다.
- 단축키 등록 중 기존 전역 단축키가 먼저 실행되어 입력을 빼앗는 문제를 수정했습니다.
- Ctrl/Alt/Shift/Win 조합 입력 중 modifier 단독 오류가 먼저 뜨지 않도록 수정했습니다.
- 넘버패드 숫자(`Num0`~`Num9`)를 일반 숫자와 분리해 단독 등록할 수 있게 했습니다.
- README의 최신 다운로드 링크와 SHA256 값을 v0.2.3 기준으로 갱신했습니다.

## [v0.2.2](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.2.2)

- 대형 GIF가 UI와 메모리를 과도하게 잡지 않도록 프레임 수/픽셀 예산 제한을 추가했습니다.
- 제한을 넘는 GIF는 전체 재생 시간을 유지하면서 프레임을 균등 샘플링합니다.
- GIF 프레임 제한과 지연시간 보존을 검증하는 synthetic GIF 테스트를 추가했습니다.
- 트레이 메뉴에 전역 단축키 설정창을 추가했습니다.
- 보이기/숨기기, 크기 프리셋/순차 변경, 이미지 열기, 좌우 반전, 항상 위, 클릭 통과, 위치 이동 단축키를 등록할 수 있게 했습니다.
- 중복 키, 불가능한 키, 토글/개별 보이기·숨기기 단축키 충돌을 안내합니다.
- 단축키 전체 비활성화 키와 트레이 메뉴의 단축키 활성화/비활성화 기능을 추가했습니다.

## [v0.2.1](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.2.1)

- 트레이 메뉴에 **업데이트 확인**을 추가했습니다.
- 새 GitHub 릴리스가 있으면 트레이 아이콘 우상단에 빨간점을 표시합니다.
- README에 v0.2.1 기준 다운로드 링크, SHA256, 최소/권장 사양 정보를 반영했습니다.

## [v0.2.0](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.2.0)

- 대형 이미지/GIF 처리 중 UI 멈춤을 줄이도록 이미지 처리를 백그라운드 worker로 옮겼습니다.
- 위치 바로가기로 보낸 구석을 기억하고, 이미지나 크기가 바뀌어도 같은 구석에 다시 붙도록 했습니다.
- 커스텀 위치에서는 크기 변경 시 중심 좌표를 유지하도록 보정했습니다.
- 손상된 anchor 설정으로 시작 시 크래시하던 문제를 수정했습니다.
- 설정 저장 fallback, 소스 실행 배치 파일, 테스트/빌드 재현성을 보강했습니다.
- 릴리즈 자동화와 CI 테스트 import 경로를 정리했습니다.

## [v0.1.0](https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.1.0)

- 첫 공개 배포입니다.
- GIF, PNG, JPG, WEBP, BMP 이미지를 프레임 없는 투명 오버레이 창으로 표시합니다.
- 애니메이션 GIF 재생을 지원합니다.
- 외곽선 기반 배경 제거와 모서리 배경색 자동 추출을 지원합니다.
- 이미 투명한 PNG/GIF는 원본 투명도를 유지합니다.
- 항상 위, 클릭 통과, 숨기기/보이기, 투명도 조절을 지원합니다.
- 모니터별 9개 위치 바로가기, 휠/프리셋/직접 입력 크기 조절을 지원합니다.
- OBS/PRISM 윈도우 캡처 대응 옵션과 트레이 아이콘 메뉴를 제공합니다.
