# DesktopOverlay 변경 내역

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
