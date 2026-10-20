"""탑뷰 카메라 열기/읽기.

⚠️ 속성 설정 순서가 fps 를 가른다(hardware/grippers/tools/arm/rollout_policy.py 실측):
    해상도 -> FOURCC   MJPG 29.9 fps
    FOURCC -> 해상도   YUY2 10.0 fps
그래서 해상도를 먼저 넣고 FOURCC 를 넣는다.

## 초점은 끄는 것만으로는 고정되지 않는다 (C920)

C920 은 초점이 움직이면 `fx`·`fy` 가 같이 변한다 — `calib/*.npz` 는 특정 초점에서 잰 값이다.
그런데 Windows DSHOW 에서 `AUTOFOCUS=0` 만 걸면 초점이 그 자리(흔히 최근접 250)에 멈춰
**바닥 마커가 한 장도 안 잡힌 적이 있다**(ArUco_C920/run_localize.py 기록). 그래서
오토포커스를 **먼저 끄고 → 초점값을 넣는다**(순서를 바꾸면 다음 재초점 때 덮어써진다).
스트림이 시작되기 전의 설정 쓰기를 흘리는 백엔드가 있어 **첫 프레임 뒤에 한 번 더** 건다.
값은 `cameras.focus` — **카메라별**이다. 팀이 쓰던 값 `{0: 5, 1: 0}`
(hardware/grippers/host/capture_dataset.py, Geti 학습 영상도 이 값으로 찍었다). 0 = 먼 곳.
1.6 m 높이에서 1~2 m 앞 바닥을 보므로 먼 쪽 끝이 맞다.

## macOS (AVFoundation)

- DSHOW 는 Windows 전용이다. 맥에서는 AVFoundation 으로 연다(`capture_backend()`).
- **AVFoundation 은 AUTOFOCUS·FOCUS 를 받지 않는다** — `set()` 이 False 를 돌려주고 아무 일도
  없다. 그래서 맥에서는 초점이 C920 펌웨어 마음대로 움직일 수 있다. 조용히 넘기지 않고 경고를 찍는다.
  초점은 카메라 쪽에서(UVC 유틸리티 등) 미리 고정해 둘 것.
- 카메라 권한(TCC)이 없으면 예외 없이 `isOpened()` 만 False 다 — 카메라가 없는 것과 구별이 안 되므로
  안내를 같이 찍는다.
- 인덱스 순서가 Windows 와 다르고, 내장 FaceTime 카메라도 인덱스 하나를 차지한다.
  `python tools/list_cameras.py` 로 인덱스마다 한 장씩 찍어 보고 `cameras.indices` 를 정한다.
"""
from __future__ import annotations

import sys
from collections.abc import Mapping
from typing import Optional, Union

import cv2
import numpy as np

Focus = Union[None, int, Mapping]

IS_MACOS = sys.platform == "darwin"

MAC_PERMISSION_HINT = ("macOS 카메라 권한일 수 있습니다 — 시스템 설정 > 개인정보 보호 및 보안 > 카메라 에서 "
                       "run_host 를 띄운 앱(터미널 · iTerm · VS Code)을 켜고 그 앱을 다시 시작하세요. "
                       "인덱스는 python tools/list_cameras.py 로 확인합니다")
MAC_FOCUS_WARNING = ("이 백엔드(AVFoundation)는 초점 고정을 받지 않습니다 — 초점이 움직이면 calib/*.npz 와 "
                     "어긋나 위치가 수 cm 틀립니다. 카메라 쪽에서 초점을 미리 고정해 두세요")


def capture_backend() -> int:
    """플랫폼별 캡처 백엔드. Windows = DSHOW(기존), macOS = AVFoundation, 그 밖 = 자동."""
    if sys.platform.startswith("win"):
        return cv2.CAP_DSHOW
    if IS_MACOS:
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_ANY


def parse_focus(text: Optional[str]):
    """명령줄 --focus 를 읽는다. '5' = 모든 카메라 5, '0=5,1=0' = 카메라별. None 은 그대로."""
    if text is None:
        return None
    if "=" not in text:
        return int(text)
    out = {}
    for part in text.split(","):
        k, v = part.split("=")
        out[int(k)] = int(v)
    return out


def focus_for(focus: Focus, index: int) -> Optional[int]:
    """이 카메라의 초점값. 카메라별 표에 없거나 음수면 None(오토포커스만 끈다)."""
    f = focus.get(int(index)) if isinstance(focus, Mapping) else focus
    return None if f is None or f < 0 else int(f)


def _lock_focus(cap, focus: Optional[int]) -> bool:
    """오토포커스를 끄고 초점을 넣는다. 백엔드가 받아들였는지(set 의 반환값)를 돌려준다."""
    ok = bool(cap.set(cv2.CAP_PROP_AUTOFOCUS, 0))
    if focus is not None:
        ok = bool(cap.set(cv2.CAP_PROP_FOCUS, focus)) and ok
    return ok


def open_cams(indices, width: int, height: int,
              focus: Focus = None) -> list[cv2.VideoCapture]:
    """카메라를 연다. focus 는 한 값(모든 카메라) 또는 {인덱스: 값}. None/음수 = 끄기만."""
    backend = capture_backend()
    caps = []
    for i in indices:
        f = focus_for(focus, i)
        cap = cv2.VideoCapture(int(i), backend)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        _lock_focus(cap, f)
        if not cap.isOpened():
            print(f"[cameras] ⚠️ 카메라 {i} 를 열 수 없습니다")
            if IS_MACOS:
                print(f"[cameras]    {MAC_PERMISSION_HINT}")
        else:
            cap.read()                  # 스트림을 띄운 뒤
            locked = _lock_focus(cap, f)    # 한 번 더 — 시작 전 설정을 흘리는 백엔드가 있다
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if (w, h) != (width, height):
                # 캘리브레이션(npz)이 1280x720 기준이라 해상도가 다르면 좌표가 통째로 틀린다.
                print(f"[cameras] ⚠️ 카메라 {i}: 요청 {width}x{height}, 실제 {w}x{h}")
            if not locked and IS_MACOS:
                # 되읽기 판정(아래)은 "0 으로 읽힌다" 같은 엉뚱한 말이 된다 — 원인을 그대로 말한다.
                print(f"[cameras] ⚠️ 카메라 {i}: {MAC_FOCUS_WARNING}")
            elif f is not None:
                got = cap.get(cv2.CAP_PROP_FOCUS)
                # 되읽은 FOCUS 는 DSHOW 에서 믿을 만하다(쓴 값 그대로 나온다, 옵시디언 실측).
                # AUTOFOCUS 되읽기는 백엔드마다 뜻이 달라 판정에 쓰지 않는다.
                if int(round(got)) != f:
                    print(f"[cameras] ⚠️ 카메라 {i}: 초점 {f} 을 넣었는데 {got:.0f} 로 읽힌다")
                else:
                    print(f"[cameras] 카메라 {i}: 초점 고정 FOCUS={f}")
            else:
                print(f"[cameras] 카메라 {i}: 초점값 없음 — 오토포커스만 껐다")
        caps.append(cap)
    return caps


def read_frames(caps) -> list[np.ndarray | None]:
    frames = []
    for cap in caps:
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        frames.append(frame if ok else None)
    return frames


def grab_frames(caps) -> None:
    """영상을 풀지 않고 한 장씩 넘긴다 — 쉬는 사이클에도 버퍼에 오래된 프레임이 쌓이지 않게(MJPEG 풀기는 retrieve 에서)."""
    for cap in caps:
        if cap.isOpened():
            cap.grab()


def release_all(caps) -> None:
    for cap in caps:
        try:
            cap.release()
        except Exception:  # noqa: BLE001 — 종료 경로
            pass
