"""카메라 인덱스를 눈으로 확인한다 — 인덱스마다 한 장씩 찍어 저장한다.

    python tools/list_cameras.py                  # 0~4 번, logs/camshot/idx{n}.png
    python tools/list_cameras.py --limit 6 --out /tmp/camshot

macOS 에서 이게 필요한 이유: 이름 목록(system_profiler) 순서와 cv2 인덱스 순서가 다르다.
2026-08-28 실측 — system_profiler [0] FaceTime [1] C920 [2] C920, cv2 [0] C920 [1] C920 [2] FaceTime.
그래서 이름으로는 못 맞추고, 찍어 보고 `config/host.yaml` 의 `cameras.indices` 를 정한다.
하나도 못 열면 거의 항상 카메라 권한 문제다(안내를 같이 찍는다). Windows 에서도 그대로 돈다.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2

HOST_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST_ROOT))

import host_config  # noqa: E402
from localization.cameras import IS_MACOS, MAC_PERMISSION_HINT, capture_backend  # noqa: E402


def mac_camera_names() -> list[str]:
    """system_profiler 가 아는 카메라 이름(참고용 — 순서가 cv2 인덱스와 다르다)."""
    try:
        out = subprocess.run(["system_profiler", "-json", "SPCameraDataType"],
                             capture_output=True, text=True, timeout=15)
        return [c.get("_name", "?") for c in json.loads(out.stdout).get("SPCameraDataType", [])]
    except Exception:  # noqa: BLE001 — 참고 정보일 뿐이다
        return []


def main() -> int:
    host_config.configure_console()
    ap = argparse.ArgumentParser(description="카메라 인덱스마다 한 장씩 찍는다")
    ap.add_argument("--limit", type=int, default=5, help="0..limit-1 을 열어 본다")
    ap.add_argument("--out", default=str(HOST_ROOT / "logs" / "camshot"))
    args = ap.parse_args()

    if IS_MACOS:
        names = mac_camera_names()
        print("system_profiler 카메라(순서는 인덱스와 다름): " + (", ".join(names) if names else "(없음)"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    opened = []
    for i in range(args.limit):
        cap = cv2.VideoCapture(i, capture_backend())
        try:
            if not cap.isOpened():
                continue
            frame = None
            for _ in range(8):              # 첫 몇 장은 노출이 덜 잡혀 어둡다
                ok, f = cap.read()
                if ok:
                    frame = f
            if frame is None:
                print(f"[{i}] 열렸지만 프레임이 없다")
                continue
            h, w = frame.shape[:2]
            path = out / f"idx{i}.png"
            cv2.imwrite(str(path), frame)
            opened.append(i)
            print(f"[{i}] {w}x{h} -> {path}")
        finally:
            cap.release()
    if not opened:
        print("열린 카메라가 없습니다.")
        if IS_MACOS:
            print(MAC_PERMISSION_HINT)
        return 1
    print(f"열린 인덱스: {opened} — 탑뷰 두 대의 인덱스를 config/host.yaml cameras.indices 에 넣으세요")
    return 0


if __name__ == "__main__":
    sys.exit(main())
