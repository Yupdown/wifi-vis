# WiFi Field

영상의 WiFi Signal Intensity Visualization을 재현하는 **Python + OpenGL 3.3 + GLFW + Dear ImGui** 데스크톱 앱입니다. 평면도와 검정 → 파랑 → 보라 → 빨강 → 노랑 → 흰색 팔레트는 제공된 영상에서 추출해 포함했습니다. 실행 시 원본 영상은 필요하지 않습니다.

## 실행

Python 3.10 이상과 OpenGL 3.3을 지원하는 그래픽 드라이버가 필요합니다. Python 3.12 / Windows에서 검증했습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

이미 의존성이 설치된 환경에서는 `python main.py`로 실행합니다.

## 조작

- **Place transmitter**를 누른 뒤 평면도를 클릭하거나 빈 곳을 더블클릭하면 송신점이 추가됩니다. 최대 32개를 지원합니다.
- 송신점의 원형 마커를 마우스로 드래그하여 이동합니다. 위치 변화에 따라 파동이 전파되고 히트맵이 갱신됩니다.
- 목록이나 마커를 클릭해 선택하고 **Power / Frequency / Phase / Enabled**를 조절합니다.
- **Remove selected**로 삭제합니다. 송신점은 최소 하나 유지됩니다.
- **Space / Pause**는 일시 정지, **Clear waves**는 파동 초기화, **Reset scene**은 송신점 초기화입니다. 정지 중 이동한 송신점은 재개 후 전파됩니다.
- **Instant wave**는 영상처럼 순간 파동과 간섭 무늬를, **Mean intensity**는 시간 평균 세기의 제곱근을 표시합니다.
- **Speed / Air loss / Wall pass / Gain**으로 시뮬레이션 속도, 공기 감쇠, 벽 전달 계수, 표시 감도를 조절합니다.
- 평면도 위의 **Open wall image...**를 누르면 파일 탐색기가 열립니다. PNG / JPEG / BMP / TIFF / WebP 이미지를 선택하면 벽과 시뮬레이션 영역이 교체됩니다. 취소하거나 읽을 수 없는 파일을 선택하면 기존 평면도가 유지됩니다.
- 흰 바탕의 검은 선과 검은 바탕의 흰 선을 자동 판별합니다. 판별이 반대이면 **Dark walls on light background**를 전환합니다. 투명 픽셀은 빈 공간으로 처리합니다. 사진보다는 벽과 빈 공간이 명확한 평면도/마스크 이미지를 사용하세요.
- 이미지 비율은 유지되며 성능을 위해 격자 크기를 조정합니다(최대 긴 변 1074, 약 36만 셀). 벽 교체 시 기존 파동은 초기화되고 송신점의 상대 위치와 설정은 유지됩니다. 정지 중 교체했다면 **Resume**으로 전파를 재개합니다.
- **Use reference**로 영상의 기본 평면도를 복원합니다. **Use walls**를 끄면 벽 없는 공간에서 전파됩니다. **Esc**는 배치 모드를 취소합니다.
- **HEATMAP → Wall visualization**은 벽의 화면 표시만 켜고 끕니다. 벽의 반사·투과 효과는 **Use walls** 설정에 따르며, 표시를 꺼도 파동은 초기화되지 않습니다. GIF에도 저장 시작 시의 벽 표시 설정이 적용됩니다.

## GIF 저장

평면도 위의 **GIF phase step**으로 각도 간격을 설정하고 **Save GIF...**를 누르면 파일 탐색기에서 저장 위치를 선택할 수 있습니다. 현재 선택된 송신기의 주파수를 기준으로, 현재 파동 상태부터 한 주기(360°)를 캡처합니다. 범위는 시작점 포함·끝점 제외이며 `ceil(360 / 간격)`개의 프레임을 생성합니다. 간격은 1°~180°, 기본값은 **7.2° → 50프레임 → 1초**입니다. 360°를 나누어떨어지게 하는 간격을 사용하면 반복 경계의 간격도 일정합니다.

- **50 FPS**, 프레임당 **20ms**, 무한 반복 GIF로 저장합니다.
- 현재 벽·히트맵 표시 모드·Gain·송신점 마커 설정을 반영하며, 설정 패널을 제외한 시뮬레이션 영역을 원래 격자 해상도로 저장합니다.
- 현재 상태를 복사하여 캡처하므로 저장 중에도 앱을 조작할 수 있고, 일시 정지 상태에서도 저장할 수 있습니다. 저장 시작 후의 설정 변경은 해당 GIF에 영향을 주지 않습니다.
- 정수 시뮬레이션 스텝 사이의 위상은 선형 보간합니다. 재생 FPS는 화면 FPS나 Speed 설정과 무관합니다.
- 진행률과 저장 결과를 표시하며 캡처 중 **Cancel**로 취소할 수 있습니다. 인코딩 중에는 짧은 파일 쓰기를 완료합니다. 저장 실패 시 기존 파일은 보존됩니다.
- 원본 LUT 기반의 공통 256색 GIF 팔레트를 사용합니다. 완전히 같은 연속 프레임은 GIF 인코더가 합칠 수 있으며 총 재생 시간은 유지됩니다.
- 서로 다른 주파수의 송신기를 함께 사용하거나 파동이 아직 퍼지는 중이면, 기준 송신기의 한 주기와 전체 장면의 반복 주기가 다를 수 있습니다.

## 시뮬레이션과 원본 재현 범위

336 × 1074 격자의 2차원 감쇠 파동 방정식을 GPU fragment shader에서 유한 차분법(FDTD)으로 계산합니다. 두 개의 부동소수점 텍스처를 번갈아 읽고 쓰며, 송신점들이 만든 파동의 중첩, 벽의 반사·투과·흡수, 외곽 흡수 경계를 계산합니다. 현재·이전 파동과 지수 이동 평균 에너지를 저장합니다. 기본 속도는 초당 720 simulation steps이고 프레임 시간에 따라 스텝 수를 조절합니다.

이 앱은 **시각화용 상대 세기 모델**입니다. GHz 값은 파장 비율을 조절하는 축척 값이며, 실제 미터 단위 평면도·재료 물성·안테나 특성이 없으므로 dBm 예측이나 실제 Wi-Fi 커버리지 측정으로 해석하지 않습니다. 송신점을 이동한 직후 이전 파동은 감쇠하며 새 위치의 파동이 유한 속도로 퍼집니다.

압축 영상에는 원본 수치 팔레트가 없으므로 관측 RGB 색을 256단계 LUT로 추출했습니다. 원본 팔레트와의 비트 단위 동일성은 확인할 수 없지만, 다른 범용 팔레트로 대체하지 않고 영상의 색상 표본을 사용합니다. 벽은 96프레임의 정적인 무채색 선을 추출한 것으로 원본 저해상도 영상의 디테일 한계가 있습니다.

## 검증 / 캡처

```powershell
python -m unittest discover -s tests -v
python tools/smoke_test.py
python tools/smoke_gif.py
python main.py --hidden --frames 120 --screenshot artifacts/screenshot.png
```

Smoke test는 실제 OpenGL 컨텍스트에서 셰이더 컴파일, 파동 전파, 송신점 추가·드래그, 일시 정지, 초기화, 송신 중지, 벽 효과와 렌더링을 검증하고 `artifacts/app-preview.png`를 저장합니다. 그래픽 컨텍스트가 필요합니다.

GIF smoke test는 실제 GPU에서 내보낸 GIF를 다시 읽어 50프레임, 프레임당 20ms, 이미지 방향, 파동 변화, 원래 시뮬레이션 상태 보존, 취소 및 저장 실패 처리를 검사합니다. 결과는 `artifacts/phase-cycle-50fps.gif`에 저장됩니다.

참조 에셋을 다시 추출하려면 선택 의존성 `opencv-python`을 설치하고 다음을 실행합니다. 추출 좌표는 제공된 234 × 586 영상 기준입니다.

```powershell
python -m pip install opencv-python
python tools/extract_reference.py "C:\Users\Yup\Downloads\bwM76wQLJI7WbsrpKUXgAsbXETzsuL7zwmhsuv4LI0Y.mp4"
```

UI 백엔드는 [pyimgui의 GLFW/OpenGL 통합](https://pyimgui.readthedocs.io/en/latest/reference/imgui.integrations.html)을 사용합니다.
