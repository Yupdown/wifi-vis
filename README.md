# WiFi Field — WebGL

기존 Python 데스크톱 앱을 **TypeScript + WebGL 2 + Dear ImGui(WebAssembly)**로 포팅한 인터랙티브 Wi-Fi 파동 시각화입니다. 기존 화면 배치, 어두운 테마, 송신점 마커, 평면도, 영상에서 추출한 팔레트를 유지합니다. 파동과 히트맵 GLSL 소스도 Python 버전과 공유하며, WebGL에서는 GLSL ES 3.00 헤더만 바꿔 사용합니다.

## 실행

Node.js 22.12 이상과 하드웨어 가속을 지원하는 브라우저가 필요합니다. Chrome에서 검증했습니다. Python 서버는 필요하지 않습니다.

```powershell
npm ci
npm run dev
```

표시되는 로컬 주소(기본 `http://127.0.0.1:5173`)에 접속합니다. WebGL 2 및 `EXT_color_buffer_float` 지원이 필요하며, 사용할 수 없으면 오류 안내가 표시됩니다. 데스크톱 배치를 유지하기 위해 최소 화면 크기는 760 × 680입니다. 더 작은 화면에서는 페이지를 스크롤해 사용합니다.

## 조작

- **Place transmitter** → 지도를 클릭하거나 빈 곳을 더블클릭해 송신점을 추가합니다. 최대 32개를 지원합니다.
- 마커를 드래그해 위치를 변경합니다. 선택한 송신기의 **Power / Frequency / Phase / Enabled**를 조절할 수 있습니다.
- **Remove selected**로 삭제합니다. 최소 하나의 송신점은 유지됩니다.
- **Pause / Space**는 정지·재개, **Clear waves**는 파동 초기화, **Reset scene**은 송신점 초기화입니다. **Esc**는 배치를 취소합니다.
- **Speed / Air loss / Wall pass**는 계산 속도·공간 감쇠·벽 결합 계수를 조절합니다.
- **Instant wave / Mean intensity**로 순간 진폭과 RMS 형태의 평균 표시를 전환합니다. **Gain**은 표시 감도만 바꿉니다.
- **Use walls**는 벽의 물리 효과를 켜고 끕니다. **Wall visualization**은 벽의 화면 표시만 바꿉니다.

## 평면도 선택

**Open wall image...**를 누르면 브라우저의 파일 선택 창이 열립니다. PNG / JPEG / BMP / WebP / TIFF를 지원하며 GIF는 첫 프레임을 사용합니다. TIFF는 포함된 디코더로 첫 페이지를 읽습니다. 이미지는 로컬 브라우저에서 처리하며 서버로 업로드하지 않습니다.

검은 바탕의 흰 선과 흰 바탕의 검은 선을 자동 판별합니다. 반대로 인식되면 **Dark walls on light background**를 전환합니다. 투명 영역은 빈 공간입니다. 비율을 유지하면서 긴 변 1074 이하, 약 36만 셀로 크기를 조절합니다. 벽 교체 시 파동은 초기화되며 송신점의 상대 위치는 유지됩니다. **Use reference**로 원본 영상의 평면도를 복원합니다. 읽을 수 없는 파일을 선택해도 기존 평면도는 유지됩니다.

## 50 FPS GIF 저장

**GIF phase step**을 조절하고 **Save GIF...**를 누릅니다. 선택된 송신기의 주파수에 맞춰 현재 상태부터 360° 한 주기를 캡처하고 `wifi-field.gif`를 다운로드합니다. 브라우저의 다운로드 설정에 따라 저장 위치를 선택하거나 다운로드 폴더에 저장됩니다. 필요하면 **Download again**으로 다시 받을 수 있습니다.

- 기본 **7.2° → 50프레임 → 1초**, **50 FPS = 프레임당 20ms**, 무한 반복입니다.
- 간격은 1°~180°입니다. 시작 위상은 포함하고 끝 위상은 제외합니다. 프레임 수는 `ceil(360 / 간격)`입니다.
- 현재 벽 표시, 히트맵 모드, Gain, 송신점 마커를 반영한 시뮬레이션 영역만 원래 격자 해상도로 저장합니다.
- 별도 GPU 상태를 복사하고 Web Worker에서 인코딩하므로 원래 시뮬레이션을 변경하지 않습니다. 정지 중에도 저장할 수 있습니다. 진행 중 설정을 바꿔도 해당 GIF는 저장 시작 시 설정을 유지합니다.
- **Cancel**로 취소합니다. 정수 계산 스텝 사이의 위상은 선형 보간합니다. 영상에서 추출한 LUT 기반의 공통 256색 팔레트를 사용합니다.
- 주파수가 서로 다른 송신기나 아직 퍼지는 중인 파동은 한 주기 뒤 장면 전체가 정확하게 반복되지 않을 수 있습니다.

## 빌드

```powershell
npm run build
npm run preview
```

배포 파일은 `dist/`에 생성됩니다. 정적 HTTP 호스팅에 이 폴더를 올리면 됩니다. 상대 경로를 사용하므로 하위 경로에서도 제공할 수 있습니다. WASM 로더와 폰트, GIF worker도 함께 포함되어 런타임 CDN이나 백엔드는 필요하지 않습니다. `index.html`을 `file://`로 직접 여는 방식은 지원하지 않습니다.

현재 jsimgui 패키지의 선택적 로더 파일명 문제는 `vite.config.ts`의 alias로 처리합니다. `node_modules`를 직접 수정할 필요가 없습니다. 빌드 시 WASM을 포함한 로더 청크 크기 안내가 나올 수 있습니다.

## 검증

```powershell
npm test
```

Windows에서는 설치된 Chrome을 사용합니다. 다른 환경에서는 먼저 `npx playwright install chromium`을 실행합니다. 실제 WebGL 컨텍스트에서 다음을 검사합니다.

- ImGui 버튼과 마우스 드래그, 송신점 추가·선택·삭제·송신 중지
- 평면도 선택·반전·복원·오류 처리, 벽 표시와 물리 계산의 독립성
- 50 FPS GIF 다운로드와 원래 시뮬레이션 상태 보존, 취소
- 고해상도 화면(DPR 2)과 창 크기 변경 후 좌표 처리
- Python GPU 기준 데이터와 동일 조건에서의 파동·픽셀 비교
- WebGL을 사용할 수 없는 브라우저의 안내

검증 이미지와 GIF는 `artifacts/`에 생성됩니다. 기준 데이터 `web-tests/fixtures/desktop-wave.json`은 Python OpenGL 버전에서 생성했으며, 재생성이 필요한 경우에만 `python tools/web_reference.py`를 실행합니다.

## 구조와 물리 모델

| 파일 | 역할 |
|---|---|
| `web/main.ts` | Dear ImGui 화면과 브라우저 입력 |
| `web/gpu.ts` | WebGL 2 부동소수점 텍스처, FBO, 파동 계산 |
| `web/model.ts` | 송신점과 위상 샘플링 |
| `web/assets.ts` | 팔레트·평면도 로딩 및 이미지 변환 |
| `web/export.ts`, `web/gif.worker.ts` | GPU 상태 복제, GIF 캡처·인코딩·다운로드 |
| `wifivis/shaders/` | Python / WebGL 공용 파동·히트맵 셰이더 |
| `wifivis/assets/` | 영상에서 추출한 원본 평면도와 LUT |

2차원 스칼라 감쇠 파동 방정식을 상하좌우 유한차분으로 계산하며, 두 RGBA32F 텍스처에 현재 진폭·이전 진폭·제곱 진폭의 이동 평균을 저장합니다. 기본 목표는 초당 720 simulation steps입니다. 선형 보간 가능한 float texture가 없는 GPU에서는 상태 텍스처의 정확한 격자 중심을 nearest로 읽습니다. 벽과 최종 표시 텍스처에는 linear sampling을 사용합니다.

이 모델은 상대적인 파동 시각화입니다. GHz는 축척된 주파수이고, 실제 미터 단위 공간·재료 물성·안테나 보정이 없으므로 dBm이나 실제 Wi-Fi 수신율을 예측하지 않습니다. 압축 영상에서 추출한 RGB LUT도 원본 수치 팔레트와 비트 단위 동일성을 보장하지는 않습니다.

기존 Python 실행과 Screen/Jiggle 합성 도구는 비교·오프라인 작업용으로 남겨 두었습니다. [기존 데스크톱 사용법](docs/desktop.md), [의존성·폰트 라이선스](THIRD_PARTY.md)를 참고하세요.
