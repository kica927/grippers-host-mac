"""basket_target.approach_nav_target — 접근 부채꼴 밖에서는 상자 중심이
아니라 부채꼴 경계선 위 점을 쫓게 한다 (2026-09-08, 두 차례 실기 사고 후속).

## 배경

CARRY_TO_DEST는 상자로 향할 때 원래 `target_center()`(상자 "중심")를 그대로
쫓았다. `check_approach_sector()`는 "지금 로봇이 남쪽 ±30° 부채꼴 반경
0.15m 안에 들어왔는가"만 판정해 FACE_BOX 전이 여부를 정할 뿐, 주행 목표
자체에는 반영되지 않았다 — 그래서 로봇이 부채꼴 밖(예: 동쪽)에서 접근
중이면 판정은 계속 실패하는데도 목표는 여전히 "중심"이라 그쪽으로 계속
다가갔다. 상자 반폭(BOX_W/2)·반길이(BOX_L/2)가 부채꼴 반경(0.15m)보다
커서, 그 상태로 반경 0.15m에 닿으면 이미 상자 옆면에 부딪힌 뒤다 —
실기에서 두 차례(queen, knight) 상자를 밀고 들어간 사고와 일치한다.

`approach_nav_target()`은 상자 중심 대신, 로봇의 지금 방위각을 부채꼴
안으로 클램프한 방향으로 부채꼴 반경만큼 뗀 점을 목표로 준다."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_HOST = Path(__file__).resolve().parent.parent / "host"
sys.path.insert(0, str(_HOST))
sys.path.insert(0, str(_HOST / "aruco"))

import basket_target as bt         # noqa: E402


def test_부채꼴_안에서_접근_중이면_방위각이_클램프되지_않는다():
    """정남쪽(부채꼴 정중앙)에서 접근하면 클램프가 안 걸려야 한다 — 목표는
    항상 부채꼴 경계선(반경 0.15m) 위에 있지만(check_approach_sector와
    반경을 공유하는 설계), 그 위치의 방위각은 로봇의 실제 방위각과 같아야
    한다. 로봇은 그 직선을 따라 그대로 다가가다 반경 0.15m에서
    check_approach_sector가 걸려 FACE_BOX로 전이되므로, 정상 경로는 예전
    (target_center를 직접 쫓던) 동작과 실질적으로 같은 궤적이 나온다."""
    cx, cy = bt.target_center("chess")
    robot_xy = (cx, cy - 0.5)   # 정남쪽, 부채꼴 밖(반경 0.15m 초과)에서 접근 중
    target = bt.approach_nav_target(robot_xy, "chess")
    south = math.radians(bt._SOUTH_BEARING_DEG)
    expected = (cx + bt.SOUTH_APPROACH_SECTOR_RADIUS_M * math.cos(south),
                cy + bt.SOUTH_APPROACH_SECTOR_RADIUS_M * math.sin(south))
    assert target == pytest.approx(expected, abs=1e-6)


def test_부채꼴_밖에서_접근하면_경계선_위_점으로_클램프된다():
    """정동쪽(남쪽 기준 90도, 부채꼴 폭 60도의 절반인 30도를 훌쩍 넘는
    각도)에서 접근하면, 목표가 상자 중심이 아니라 남쪽 +30도 방향의
    부채꼴 경계선(반경 0.15m) 위 점이어야 한다 — 상자를 관통하지 않고
    그 경계를 따라 돌아 들어오게 하는 것이 이 함수의 목적이다."""
    cx, cy = bt.target_center("chess")
    robot_xy = (cx + 0.5, cy)   # 정동쪽에서 접근
    target = bt.approach_nav_target(robot_xy, "chess")

    # 남쪽(-90도) 기준 +half(=+30도)로 클램프된 방향 = -60도.
    half = bt.SOUTH_APPROACH_SECTOR_DEG / 2.0
    expected_bearing = math.radians(bt._SOUTH_BEARING_DEG + half)
    expected = (cx + bt.SOUTH_APPROACH_SECTOR_RADIUS_M * math.cos(expected_bearing),
                cy + bt.SOUTH_APPROACH_SECTOR_RADIUS_M * math.sin(expected_bearing))
    assert target == pytest.approx(expected, abs=1e-6)

    # 목표가 정확히 부채꼴 경계선(반경) 위에 있어야 한다 — 상자 중심을
    # 그대로 쫓았다면 이 거리가 훨씬 컸을 것이다.
    dist = math.hypot(target[0] - cx, target[1] - cy)
    assert dist == pytest.approx(bt.SOUTH_APPROACH_SECTOR_RADIUS_M, abs=1e-6)


def test_목표는_로봇의_거리와_무관하게_같은_방위각을_쫓는다():
    """부채꼴 밖에서 접근할 때 목표는 항상 부채꼴 경계선(반경 고정) 위에
    있어야 한다 — 로봇이 멀든 가깝든(둘 다 부채꼴 밖) 상자를 관통하는
    방향으로 안 당겨져야 한다."""
    cx, cy = bt.target_center("chess")
    near = bt.approach_nav_target((cx + 0.3, cy), "chess")
    far = bt.approach_nav_target((cx + 1.0, cy), "chess")
    assert near == pytest.approx(far, abs=1e-6)


def test_부채꼴_경계에_걸친_45도는_클램프되지_않는다():
    """부채꼴 폭이 ±30도이므로, 그 안쪽인 45도... 가 아니라 정확히 half
    이내(예: 20도)는 클램프 없이 실제 방위각 그대로 써야 한다."""
    cx, cy = bt.target_center("chess")
    bearing_deg = bt._SOUTH_BEARING_DEG + 20.0   # half(30도) 이내
    robot_xy = (cx + 0.3 * math.cos(math.radians(bearing_deg)),
                cy + 0.3 * math.sin(math.radians(bearing_deg)))
    target = bt.approach_nav_target(robot_xy, "chess")
    expected = (cx + bt.SOUTH_APPROACH_SECTOR_RADIUS_M * math.cos(math.radians(bearing_deg)),
                cy + bt.SOUTH_APPROACH_SECTOR_RADIUS_M * math.sin(math.radians(bearing_deg)))
    assert target == pytest.approx(expected, abs=1e-6)
