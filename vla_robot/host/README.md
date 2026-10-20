# vla_robot Host (노트북)

탑뷰 카메라 2대 + ArUco 로 로봇 위치를, Geti 검출기로 기물 위치를 잡고, 미션 FSM 이 매 사이클
`HostCommand` 를 Pi 로 보낸다. 규격은 `../ros2_ws/src/vla_common/vla_common/protocol.py` 하나뿐이다.

## 설치 (Windows, Python 3.11)

```powershell
cd vla_robot\host
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt          # vla_common 을 -e 로 함께 설치
pip install geti-sdk==2.13.1             # 검출기를 쓸 때만
```

`vla_common` 설치를 건너뛰어도 `host_config.py` 가 경로를 자동으로 얹는다.

## 설치·실행 (macOS, Apple Silicon, Python 3.11)

```zsh
brew install python@3.11
cd vla_robot/host
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install geti-sdk==2.13.1
```

코드는 Windows 와 한 벌이다 — 플랫폼 분기는 아래 네 곳뿐이다.

| 곳 | Windows | macOS |
|---|---|---|
| 카메라 백엔드(`localization/cameras.py`) | DSHOW | AVFoundation |
| 초점 고정 | AUTOFOCUS=0 → FOCUS 값 | **안 된다** — AVFoundation 이 받지 않는다. 경고를 찍는다 |
| UI 창 높이(`view/web_view.py`) | 작업 영역(작업 표시줄 제외) | 작업 영역(메뉴 막대·Dock 제외, `osascript`). 13인치 맥북 770 pt — 고정 860 이면 아래가 잘린다 |
| 검출기 장치(`perception/detector.py`) | OpenVINO `GPU.0`(iGPU), 안 되면 CPU | 처음부터 CPU(맥용 OpenVINO 에는 GPU 가 없다). M 시리즈 한 장 약 0.19 s |

처음 한 번 할 일:

1. **권한** — 시스템 설정 > 개인정보 보호 및 보안 > **카메라**·**마이크** 에서 run_host 를 띄우는 앱(터미널 · iTerm ·
   VS Code)을 켠다. 권한이 없으면 예외 없이 "카메라를 열 수 없습니다"만 나온다(안내를 같이 찍는다).
2. **카메라 인덱스** — 맥은 순서가 Windows 와 다르고 내장 FaceTime 카메라도 인덱스 하나를 차지한다.
   C920 두 대를 꽂고 `python tools/list_cameras.py` → `logs/camshot/idx*.png` 를 보고 `config/host.yaml` 의
   `cameras.indices` 를 맞춘다(2026-08-28 실측: 외장이 먼저 [0][1], FaceTime 이 [2]). **C920 없이 실기 모드로 띄우면
   0번 = FaceTime 이 열린다.**
3. **초점** — 맥에서는 OpenCV 로 C920 초점을 고정할 수 없다. 초점이 움직이면 `calib/*.npz` 와 어긋나 위치가 수 cm 틀린다.
   카메라 쪽 유틸리티로 초점을 고정해 두거나, 정확도가 중요한 날은 Windows 에서 돌린다.
4. **모델** — Geti 배포 폴더를 `models/geti_deployment`, 손 모델을 `models/hand_landmarker.task` 에 둔다(저장소 밖).
5. **Claude 키** — `~/.zshrc` 에 `export ANTHROPIC_API_KEY=<키>` 를 넣고 터미널을 새로 연다.

실행 명령은 아래 "실행"과 같다(`python` 은 venv 안의 3.11).

맥에서 알아 둘 것:

- 기동할 때 `objc[...]: Class AVFFrameReceiver is implemented in both ... cv2 ... av ...` 경고가 뜰 수 있다.
  OpenCV 와 PyAV(faster-whisper 의존)가 같은 FFmpeg 장치 라이브러리를 각자 들고 와서 나는 경고다. 카메라는 OpenCV 자체
  AVFoundation 경로로 열고 PyAV 의 장치 입력은 쓰지 않으므로 동작에는 영향이 없다(2026-10-20 시뮬 · 검출기 · UI 확인).
- `../ros2_ws/src/vla_common/test` 중 `test_arm_units` · `test_config` 일부는 Pi 설정(`vla_robot_bringup/config`)을
  읽는다 — 이 저장소에는 Host 만 있으므로 실패한다. 규약 테스트(`test_protocol.py`)는 돈다.

## 준비물

- **카메라 캘리브레이션**: `calib/cam0.npz`, `calib/cam1.npz` (기존 `hardware/grippers_topview/calib` 에서 복사해 둠).
  카메라를 바꾸거나 초점이 달라지면 `python tools/calibrate_camera.py --cam 0` 으로 다시 잰다.
  파일이 없으면 근사값으로 돌며 큰 경고를 찍는다(수 cm 오차).
- **Geti 모델**(87 MB, 저장소에 넣지 않음):
  `hardware\grippers_topview\geti_sdk-deployment\deployment` 폴더를 `host\models\geti_deployment` 로 복사.
- **손 검출 모델**(선택, 7.8 MB, 저장소에 넣지 않음): `requirements.txt` 의 mediapipe +
  `models/hand_landmarker.task`
  (https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task).
  없으면 경고만 하고 손 없이 돈다. 손은 지도에 주황 원("hand L2")으로만 표시한다 — 미션은 아직 쓰지 않는다.
  카메라에서 잡히는지는 `python tools/hand_probe.py --live` 로 따로 본다.
- **실측값**: `config/host.yaml` — 마커 높이·바닥 마커 좌표·상자 좌표·yaw_offset.
  모르는 키가 있으면 기동을 거부한다.

## 실행

```powershell
python run_host.py --sim                      # 차량·카메라 없이 전체 흐름 확인
python run_host.py --sim --step               # n 키로 한 단계씩
python run_host.py --detector none --show-cams  # 카메라+ArUco 만 확인(명령은 콘솔 출력)
python run_host.py --pi-ip 192.168.0.7        # 실기
python tools/udp_teleop.py --pi-ip 192.168.0.7  # ArUco 없이 Pi 주행/팔 작업만 시험
```

### 화면

기본 화면은 **팀원 시연 UI**(`ui/grippers-ui.html`, 세로 432×768)다. run_host 가 `127.0.0.1:8765` 에
작은 HTTP 서버를 띄우고 크롬/엣지 `--app` 창(주소창 없음)으로 연다 — 윈도우·맥 모두 추가 설치가 없다
(pywebview 불필요). 둘 다 없으면 기본 브라우저로 열린다. **창에서 `q` = 종료**(창도 닫힌다). 창을 X 로 닫으면
run_host 는 계속 도니 그때는 터미널에서 Ctrl+C.

- 실행 화면: 지도(로봇·기물·경로·바구니·손) + 단계(1/4 접근 → 2/4 집기 → 3/4 운반 → 4/4 놓기)와 진행률
- 트레이: 비상 정지(해제는 카드의 "초기화 후 재개") · AUTO/MANUAL · Reset(두 번) · Prev/Next
- 트레이 **Map** 버튼(또는 `v`) = 대기 중에도 지도 + 장판 위 기물 목록
- 키: `q` 종료 · `v` 지도 보기(대기 중) · `Esc` 비상 정지 · `Space` 마이크 · `→`/`←` 다음/이전(수동) · `d` 디버그(전압 등)
- **입력창·마이크 = 사람 지시**(아래 "지시"). 마이크는 노트북 내장 마이크 → whisper(오프라인) → 들은 문장 확인 → 전송
- UI 파일은 팀원 원본을 그대로 두고 `arena.js` 의 `vla_robot:` 주석 자리만 고쳤다(장판 1.98×1.83 · 손 표시).
  상태 문구는 `view/ui_state.py`, 서버·창은 `view/web_view.py`, 브라우저 쪽 연결은 `ui/host_bridge.js`.

### 지시 (Claude API)

입력창에 문장을 쓰면 `mission/instruction.py` 가 Claude(`claude-opus-5-5`, effort low)로
**어떤 기물(라벨 여럿 가능) · 하나/전부 · 정리(바구니)/가져오기**를 해석하고, FSM 이 그 기물만 고른다.
예: "퀸을 바구니에 넣어줘" · "체스 말만 전부 정리해줘" · "자유롭게 움직이는 말 정리해".
라벨은 그 순간 작업 구역에 보이는 것 중에서만 고른다. 해석을 못 하면 카드에 이유와 함께 보이는 기물 목록이 떠서 직접 고를 수 있다.

- **키**: `ANTHROPIC_API_KEY` **사용자 환경변수**(파일·저장소에 두지 않는다). 없으면 입력할 때 카드로 알린다.
  PowerShell: `[Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', '<키>', 'User')` → 터미널을 새로 연다.
- **확인**: `python tools/try_instruction.py "체스 말만 전부 정리해줘"` (부를 때마다 요금)
- **모드**(`instruction.mode`): `auto` = 보이는 기물을 모두 정리하되 지시가 오면 그것부터 ·
  `instructed` = 지시가 있을 때만 움직인다. 초기화(Reset)는 지시도 취소한다.
- **가져오기**("가져와") = 사람 손에 건네기. 지시를 받을 때 탑뷰에 손이 보여야 접수한다(없으면 카드 —
  "바구니에 넣기"로 바꿀 수 있다). 손 검출은 CPU 를 아끼려고 **명령 해석·마이크 입력·손 대기·건네기 중에만** 돈다 —
  해석이 손 확인보다 먼저 끝나면 최대 2 s "손을 찾는 중"으로 기다린다. 집은 뒤 보이는 손에서 가장 가까운 위치(F1~R3)의 **정차점**
  (`handover.spots`: [손 x, 손 y, 정차 x, 정차 y])으로 가서 손 쪽을 보고(남는 각도는 팔 base),
  Pi 에 PLACE(`place_pose=handover`)를 보낸다. Pi 는 `arm_poses.yaml` 의 **handover**(ㄱ자) 자세로 가서
  `place.handover_wait_s`(1 s) 기다린 뒤 연다. 정차점에서 손이 `hand_wait_s`(20 s) 동안 안 보이면 바구니로 간다.
  handover 자세는 10-05 교육장에서 실측했다(그리퍼 끝 높이 약 55 cm). 10-05 · 10-08 "룩 가져와" 성공.
- 시뮬에서 손 두기: `python run_host.py --sim --sim-hand L2` (지시는 입력창으로 — Claude 키 필요)

### 음성 (노트북 마이크)

마이크 버튼(또는 `Space`)을 누르고 말하면 말이 끝날 때 자동으로 멈추고(`voice.silence_s` 0.9 s),
`voice/voice_input.py` 가 faster-whisper(small, int8, CPU — 한 문장 ~2.6 s)로 글자로 바꾼다. 들은 문장이 접수 화면에
뜨면 **전송**을 눌러야 해석으로 간다(whisper 는 비슷한 소리의 다른 낱말을 낸다 — 확인 단계가 안전장치).

- 모델: `models/whisper-small`(464 MB, 저장소 밖) — `python tools/try_voice.py --download` 로 한 번 받는다.
  이 노트북은 사용자 환경변수 `HF_HOME` 이 F: 드라이브를 가리켜, 도구가 그 프로세스에서만 캐시를 돌려 받는다.
- 시험: `python tools/try_voice.py` (마이크 한 문장) · `--wav 파일.wav`
- 인식 힌트 낱말은 `voice.prompt`. 끄려면 `voice.enabled: false`.

예전 OpenCV 지도는 `--view cv`(또는 `view.kind: cv`). 키: `q` 종료 · `space` ESTOP 래치(`r` 로만 해제) ·
`r` 리셋 · `n` 다음(수동) · `p` 이전 · `m` 수동/자동 전환

## 상태 흐름

```
SEARCH_TARGET -> APPROACH_PIECE -> GRASP -> CARRY_TO_DEST -> NUDGE_BOX -> PLACE -> SEARCH_TARGET
                                     |            └-> FACE_HAND -> PLACE(handover)   ("가져와")
                                     | 실패: 1번 더 시도, 그래도 실패면 기물 보류(90 s) 후 SEARCH
                                                     투입 실패: 상자 앞 맞추기부터 재시도(2회), 넘으면 HALTED
```

전선 상태: SEARCH/HALTED=IDLE(stop) · APPROACH_PIECE=APPROACH · CARRY/FACE_HAND=CARRY · NUDGE=APPROACH_BOX ·
GRASP/PLACE=해당 작업(stop) · ESTOP 래치=ESTOP.

주행·정차·회전의 자세한 규칙과 설정 키는 [`docs/behavior.md`](../../docs/behavior.md).

- 매 사이클 명령을 반드시 하나 보낸다. pose 를 잃으면 stop 을 보낸다.
- GRASP/PLACE 중에는 pose 와 무관하게 같은 상태를 계속 보낸다(팔이 마커를 가리는 건 정상).
- 작업 완료는 `JobTracker` 로 판정한다(Pi 가 결과를 매 패킷 반복 → UDP 유실에 안전).

## 테스트

```powershell
python -m pytest -q tests
python tools/sim_regress.py              # 교육장 배치로 6기물 판 전체를 시뮬에서(회귀 점검)
python tools/sim_regress.py rand 7 20    # 무작위 배치 20개
```

⚠️ 집에서는 카메라를 여는 실행(실기 모드 run_host)을 하지 말 것 — 노트북에 붙은 다른 카메라(휴대폰 연결 등)가
0번으로 열린다. 인식 부하를 잴 때는 합성 영상으로 잰다.
