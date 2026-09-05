""""가져와"("fetch") 구현 — FACE_BOX/NUDGE_BOX/PLACE(바구니 정렬)를 건너뛰고
FETCH_DROP에서 무조건 투하한다 (사용자 지시, 2026-09-06).

## 배경

instruction_resolver.py는 "가져와" 의도(intent="fetch")를 이미 판단하고
있었고, run_mission.py도 그 경우 `fsm.set_instruction(label,
dest_xy=mcfg.DELIVER_HERE_XY)`를 이미 부르고 있었다 — 라벨 오버라이드와
목적지 오버라이드 자체는 있었다. 하지만 CARRY_TO_DEST 도착 뒤로 이어지는
FACE_BOX/NUDGE_BOX/PLACE는 전부 "목적지에 실제 바구니가 있다"는 전제로
라이다 정렬·INSERT 라이다 게이트를 도는 코드였다 — dest_box_name이
None인 "가져와" 경로에선 그 전제 자체가 성립하지 않아, 실제로는 끝까지
도달할 방법이 없었다("아직 구현이 없다"던 사용자 판단이 맞았다).

이 파일은 "가져와"가 CARRY_TO_DEST 도착 후 FETCH_DROP으로 곧장 가서(정렬
없이) 무조건 투하하고, 그 뒤 RETURN_HOME으로 돌아가 다음 사용자 명령을
기다리는지 확인한다.

Pi 쪽은 건드리지 않는다 — FETCH_DROP은 Pi에 이미 있는 DEBUG_FORCE_INSERT
우회(원래 수동 시험용, domain/task/baseline_mission.py의
BaselineCarryState.execute() 참고)를 그대로 재사용한다. 그래서 여기 쓰는
가짜 Pi(FetchDoneAutoDonePi)도 "FETCH_DROP을 받으면 그 자리에서 바로
PLACE_DONE"이라는, DEBUG_FORCE_INSERT가 실제로 하는 일(라이다 게이트
없이 곧장 완료)을 그대로 흉내낸다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HOST = Path(__file__).resolve().parent.parent / "host"
sys.path.insert(0, str(_HOST))
sys.path.insert(0, str(_HOST / "aruco"))

import mission_config as mcfg                # noqa: E402
from mission import MissionFSM, State        # noqa: E402
from vehicle_link import _STATE_TO_PI, MissionState, encode, MissionCommand  # noqa: E402

from conftest import PiSim                    # noqa: E402
from test_instruction import AutoDonePi       # noqa: E402

MAX_STEPS = 900


class FetchDoneAutoDonePi(AutoDonePi):
    """FETCH_DROP을 받으면 그 자리에서 곧장 PLACE_DONE으로 답한다 — Pi의
    DEBUG_FORCE_INSERT(라이다 게이트 없이 곧장 완료)를 흉내낸다. GRASP은
    AutoDonePi가, 그 외(PLACE 등)는 PiSim의 실제 판정이 그대로 처리한다."""

    def poll_status(self) -> str:
        last_status = self.sent[-1][1] if self.sent else None
        if last_status == "FETCH_DROP":
            return "PLACE_DONE"
        return super().poll_status()


def _run_until(fsm, link, pmap, predicate, max_steps=MAX_STEPS):
    for _ in range(max_steps):
        fsm.step(link.pose(), pmap, link)
        if predicate(fsm):
            return
    raise AssertionError(
        f"{max_steps} 사이클 안에 조건에 도달하지 못했다 — 상태 {fsm.state.name}")


def test_STATE_TO_PI에서_FETCH_DROP은_DEBUG_FORCE_INSERT로_매핑된다():
    assert _STATE_TO_PI["FETCH_DROP"] == MissionState.DEBUG_FORCE_INSERT
    hc = encode(MissionCommand("stop", "FETCH_DROP", 0.0, 0.0, 0.0))
    assert hc.state == MissionState.DEBUG_FORCE_INSERT


def test_가져와는_FACE_BOX_NUDGE_BOX_PLACE를_거치지_않고_FETCH_DROP으로_간다():
    fsm = MissionFSM()
    link = FetchDoneAutoDonePi(x=0.3, y=0.6, yaw_deg=0.0)
    pmap = {"queen": [(0.5, 0.6)]}

    applied = fsm.set_instruction("queen", dest_xy=mcfg.DELIVER_HERE_XY)
    assert applied is True

    visited = set()
    for _ in range(MAX_STEPS):
        fsm.step(link.pose(), pmap, link)
        visited.add(fsm.state)
        if fsm.state in (State.FETCH_DROP, State.RETURN_HOME) and fsm.state != State.CARRY_TO_DEST:
            if fsm.state == State.FETCH_DROP:
                break
    else:
        raise AssertionError(f"{MAX_STEPS} 사이클 안에 FETCH_DROP에 못 갔다 — "
                              f"상태 {fsm.state.name}")

    assert State.FACE_BOX not in visited, "가져와인데 FACE_BOX를 거쳤다"
    assert State.NUDGE_BOX not in visited, "가져와인데 NUDGE_BOX를 거쳤다"
    assert State.PLACE not in visited, "가져와인데 PLACE를 거쳤다"


def test_FETCH_DROP_완료후_RETURN_HOME으로_가고_목표가_비워진다():
    fsm = MissionFSM()
    link = FetchDoneAutoDonePi(x=0.3, y=0.6, yaw_deg=0.0)
    pmap = {"queen": [(0.5, 0.6)]}

    fsm.set_instruction("queen", dest_xy=mcfg.DELIVER_HERE_XY)
    _run_until(fsm, link, pmap, lambda f: f.state == State.RETURN_HOME)

    assert fsm.target_label is None
    assert fsm._target_xy is None
    assert fsm.dest_xy is None
    assert fsm.dest_box_name is None


def test_FETCH_DROP은_Pi에_FETCH_DROP_상태를_실어_보낸다():
    fsm = MissionFSM()
    link = FetchDoneAutoDonePi(x=0.3, y=0.6, yaw_deg=0.0)
    pmap = {"queen": [(0.5, 0.6)]}

    fsm.set_instruction("queen", dest_xy=mcfg.DELIVER_HERE_XY)
    _run_until(fsm, link, pmap, lambda f: f.state == State.RETURN_HOME)

    assert any(status == "FETCH_DROP" for _cmd, status in link.sent)
