"""CARRY_TO_DEST가 상자로 향할 때 진입각을 반영하는지 (2026-09-08, 두 차례
실기 사고 후속 — queen/knight를 옮기다 접근 부채꼴 밖 방위에서 상자 옆면에
부딪혀 밀고 들어간 사고).

이 파일은 mission.MissionFSM._approach()를 가로채, CARRY_TO_DEST가

  1. 상자로 향할 때는 basket_target.target_center()가 아니라
     basket_target.approach_nav_target()이 계산한 점을 nav_target으로
     넘기는지,
  2. 상자 중심까지 거리가 위험 반경(BOX_L/2 + BOX_APPROACH_MARGIN_M) 안이면
     allow_escape=False를 넘기는지, 밖이면 True를 넘기는지

를 확인한다. 실제 주행 로직(navigator)은 각각 test_basket_target_
approach_nav_target.py / test_drive_sequencer_oscillation_escape.py가
따로 검증하므로, 여기서는 mission.py의 배선만 본다."""

from __future__ import annotations

import math
import sys
from pathlib import Path

_HOST = Path(__file__).resolve().parent.parent / "host"
sys.path.insert(0, str(_HOST))
sys.path.insert(0, str(_HOST / "aruco"))

import basket_target                    # noqa: E402
import config as cfg                    # noqa: E402
import mission_config as mcfg           # noqa: E402
from mission import MissionFSM, State   # noqa: E402
import mission                          # noqa: E402

from conftest import PiSim              # noqa: E402


def _setup_fsm(dest_box_name: str) -> MissionFSM:
    fsm = MissionFSM()
    fsm.state = State.CARRY_TO_DEST
    fsm.target_label = "queen"
    fsm._target_xy = (0.0, 0.0)
    fsm.dest_xy = mission._box_front_xy(dest_box_name)
    fsm.dest_box_name = dest_box_name
    return fsm


def test_상자로_향할_때는_target_center_대신_approach_nav_target을_넘긴다(monkeypatch):
    calls: list = []
    real_approach = MissionFSM._approach

    def _spy(self, pose, robot_xy, target_xy, obstacles, target_label, link,
             allow_escape=True):
        calls.append((target_xy, allow_escape))
        return real_approach(self, pose, robot_xy, target_xy, obstacles,
                             target_label, link, allow_escape=allow_escape)

    monkeypatch.setattr(MissionFSM, "_approach", _spy)

    fsm = _setup_fsm("chess")
    cx, cy = basket_target.target_center("chess")
    # 위험 반경 밖(정동쪽 0.5m)에서 접근 — 부채꼴 밖이라 클램프가 걸려야 한다.
    link = PiSim(x=cx + 0.5, y=cy, yaw_deg=180.0)

    fsm.step(link.pose(), {}, link)

    assert calls, "CARRY_TO_DEST에서 _approach가 호출되지 않았다"
    nav_target, _allow_escape = calls[0]
    expected = basket_target.approach_nav_target((cx + 0.5, cy), "chess")
    assert nav_target == expected, (
        f"nav_target이 approach_nav_target() 결과가 아니다 — {nav_target!r} "
        f"!= {expected!r} (target_center를 그대로 썼다면 {(cx, cy)!r})")
    assert nav_target != (cx, cy), "부채꼴 밖인데도 여전히 상자 중심을 그대로 쫓는다"


def test_위험_반경_안이면_allow_escape가_False다(monkeypatch):
    calls: list = []
    real_approach = MissionFSM._approach

    def _spy(self, pose, robot_xy, target_xy, obstacles, target_label, link,
             allow_escape=True):
        calls.append(allow_escape)
        return real_approach(self, pose, robot_xy, target_xy, obstacles,
                             target_label, link, allow_escape=allow_escape)

    monkeypatch.setattr(MissionFSM, "_approach", _spy)

    fsm = _setup_fsm("chess")
    cx, cy = basket_target.target_center("chess")
    danger_radius = cfg.BOX_L / 2.0 + mcfg.BOX_APPROACH_MARGIN_M
    # 위험 반경보다 살짝 안쪽, 정남쪽에서 접근.
    link = PiSim(x=cx, y=cy - (danger_radius - 0.02), yaw_deg=90.0)

    fsm.step(link.pose(), {}, link)

    assert calls and calls[0] is False, (
        "상자 중심까지 위험 반경 안인데도 allow_escape=True로 넘어갔다 — "
        "ESCAPE(정렬 무시 강제 전진)가 여전히 발동할 수 있다")


def test_위험_반경_밖이면_allow_escape가_True다(monkeypatch):
    calls: list = []
    real_approach = MissionFSM._approach

    def _spy(self, pose, robot_xy, target_xy, obstacles, target_label, link,
             allow_escape=True):
        calls.append(allow_escape)
        return real_approach(self, pose, robot_xy, target_xy, obstacles,
                             target_label, link, allow_escape=allow_escape)

    monkeypatch.setattr(MissionFSM, "_approach", _spy)

    fsm = _setup_fsm("chess")
    cx, cy = basket_target.target_center("chess")
    danger_radius = cfg.BOX_L / 2.0 + mcfg.BOX_APPROACH_MARGIN_M
    # 위험 반경보다 한참 밖 — 방 반대쪽에서 접근하는 정상적인 CARRY_TO_DEST 초반.
    link = PiSim(x=cx, y=cy - (danger_radius + 0.5), yaw_deg=90.0)

    fsm.step(link.pose(), {}, link)

    assert calls and calls[0] is True, (
        "상자에서 멀리 떨어져 있는데도 allow_escape=False로 넘어갔다 — "
        "상자와 무관한 일반 주행에서 ESCAPE 안전판이 꺼지면 안 된다")


def test_상자가_아니라_사람에게_가져다주는_경우는_그대로_dest_xy를_쫓는다(monkeypatch):
    """dest_box_name이 None이면(예: "가져와") 기존처럼 고정 지점(dest_xy)을
    쫓아야 한다 — 이번 수정이 그 경로를 건드리면 안 된다."""
    calls: list = []
    real_approach = MissionFSM._approach

    def _spy(self, pose, robot_xy, target_xy, obstacles, target_label, link,
             allow_escape=True):
        calls.append((target_xy, allow_escape))
        return real_approach(self, pose, robot_xy, target_xy, obstacles,
                             target_label, link, allow_escape=allow_escape)

    monkeypatch.setattr(MissionFSM, "_approach", _spy)

    fsm = MissionFSM()
    fsm.state = State.CARRY_TO_DEST
    fsm.target_label = "queen"
    fsm._target_xy = (0.0, 0.0)
    fsm.dest_xy = (0.9, 0.3)
    fsm.dest_box_name = None

    link = PiSim(x=0.5, y=0.5, yaw_deg=90.0)
    fsm.step(link.pose(), {}, link)

    assert calls
    nav_target, allow_escape = calls[0]
    assert nav_target == fsm.dest_xy
    assert allow_escape is True
