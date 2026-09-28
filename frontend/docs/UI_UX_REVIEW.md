# Image Processing Studio UI/UX 변경사항

## 이미지 실험실

- 입력 Viewer → Settings → 결과 Viewer의 3열 작업 흐름으로 구성했습니다.
- Settings에서 Operation 또는 Quick Run을 선택하고 같은 위치의 Run 버튼으로 실행합니다.
- 입력과 결과 Viewer 각각에 Histogram, Image Statistics, Image Feature, Image Analysis 탭을 둡니다.
- 결과 Viewer의 Apply는 결과를 새 입력으로 지정하고 직전 입력을 History에 추가합니다. History 패널은 열고 닫을 수 있습니다.
- Viewer의 Save는 지원 브라우저에서 파일 저장 대화상자를 열며, 다른 브라우저에서는 다운로드를 사용합니다.

## ROI 편집

- Recipe Studio의 ROI Crop 노드에서 이미지 파일을 로컬 미리보기로 열고 드래그해 영역을 지정할 수 있습니다.
- 픽셀/상대 좌표 모드에 맞춰 ROI 숫자 값도 함께 갱신됩니다.
- 미리보기 이미지는 레시피에 포함하거나 서버에 전송하지 않습니다. 저장되는 값은 ROI 좌표뿐입니다.

## Synthetic NG Generator

- Source Preview, Result 탭, 다중 Candidate 선택, 품질 지표, Asset Library, Diffusion Runtime을 유지하고 Source 및 결과 이미지에 저장 기능을 추가했습니다.
- 화면 높이가 부족할 때 아래 Asset Library와 Diffusion Runtime 영역까지 스크롤할 수 있게 했습니다.
- 결과의 Mask/Difference 탭에는 체크무늬 배경을 사용해 투명 영역과 변경 영역을 알아보기 쉽게 했습니다.
- Method Parameters의 JSON 입력은 모델별 고급 설정을 노출하는 장점이 있지만 초보 사용자에게 어렵습니다. 추후 method metadata 기반 입력 폼으로 옮기는 것이 다음 UX 개선 후보입니다.

## 이미지 저장 동작

- 저장은 브라우저 로컬에서 처리하며 파일을 API에 다시 보내지 않습니다.
- 최신 Chrome/Edge 계열에서는 저장 대화상자에서 경로와 파일명을 선택합니다. File System Access API가 없는 브라우저에서는 기본 다운로드 위치에 저장됩니다.
