"""PLACE(INSERT) 완료 후 어디로 가는가 — RETURN_HOME은 "더 찾을 게 없을 때"만.

## 왜 (히스토리)

- 2026-09-02, 시연용으로 PLACE 완료 후 SEARCH_TARGET으로 곧장 가지 않고
  매번 RETURN_HOME을 한 번 거치도록 바뀌었다. 바구니 바로 앞은 매번 접근
  각도·거리가 조금씩 다른 자리라, PLACE가 끝나자마자 그 자리에서
  SEARCH_TARGET을 시작하면 매 라운드가 다른 자리에서 시작돼 시연이 매번
  다르게 보였기 때문이다.
- 2026-09-06, 사용자 지시로 그 "완료 후 항상 RETURN_HOME"을 되돌렸다 —
  실기로 보니 그 왕복 자체가 기물마다 불필요한 이동을 늘렸다. 원래(그
  이전) 설계대로: 화면에 아직 찾을 기물이 남아 있거나 대기 중인 사용자
  지시가 있으면 그 자리에서 곧장 SEARCH_TARGET으로 넘어가고, 더 찾을 게
  없을 때만 RETURN_HOME을 거쳐 대기한다.

`_skip_target`(기물을 포기했을 때 실패한 자리에 남지 않으려고
RETURN_HOME을 거치는 것)은 이유가 달라 이번 변경과 무관하다 — 이 파일은
PLACE(INSERT) 성공 경로만 다룬다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HOST = Path(__file__).resolve().parent.parent / "host"
sys.path.insert(0, str(_HOST))
sys.path.insert(0, str(_HOST / "aruco"))

import mission_config as mcfg               # noqa: E402
from mission import MissionFSM, State        # noqa: E402

from conftest import PiSim                    # noqa: E402

MAX_STEPS = 900

# 화면에 다른 체스말(knight)이 남아 있는 경우 — PLACE 완료 후 RETURN_HOME을
# 거치지 않고 곧장 SEARCH_TARGET으로 가야 한다.
_OTHER_CHESS_PIECE_REMAINS = {"knight": [(0.9, 0.9)]}

# 화면에 더 찾을 기물이 없는 경우 — PLACE 완료 후 RETURN_HOME으로 가서
# 대기해야 한다.
_NO_PIECE_LEFT = {}


def test_남은_기물이_있으면_PLACE_완료_후_곧장_SEARCH_TARGET으로_간다():
    sim = PiSim()
    fsm = MissionFSM()
    assert fsm.begin_carrying("rook")

    # PLACE -> NUDGE_BOX 보정 왕복(정상 동작)과 진짜 완료를 구분해야 한다 —
    # "직전이 PLACE였고 지금이 (RETURN_HOME이 아니라) SEARCH_TARGET"인
    # 순간만 완료로 본다(tests/test_basket_close_loop.py 의
    # _run_to_place_done 과 같은 이유).
    was_place = False
    for _ in range(MAX_STEPS):
        was_place = fsm.state == State.PLACE
        fsm.step(sim.pose(), _OTHER_CHESS_PIECE_REMAINS, sim)
        if was_place and fsm.state == State.SEARCH_TARGET:
            break
        if was_place and fsm.state == State.RETURN_HOME:
            raise AssertionError(
                "남은 기물(knight)이 있는데도 RETURN_HOME을 거쳤다 — "
                "곧장 SEARCH_TARGET으로 갔어야 한다")
        if was_place and fsm.state not in (State.PLACE, State.NUDGE_BOX):
            raise AssertionError(
                f"PLACE에서 예상 밖의 상태({fsm.state.name})로 넘어갔다")
    else:
        raise AssertionError("PLACE가 SEARCH_TARGET으로 끝나지 않았다")


def test_더_찾을_기물이_없으면_PLACE_완료_후_RETURN_HOME으로_간다():
    sim = PiSim()
    fsm = MissionFSM()
    assert fsm.begin_carrying("rook")

    was_place = False
    for _ in range(MAX_STEPS):
        was_place = fsm.state == State.PLACE
        fsm.step(sim.pose(), _NO_PIECE_LEFT, sim)
        if was_place and fsm.state == State.RETURN_HOME:
            break
        if was_place and fsm.state not in (State.PLACE, State.NUDGE_BOX):
            raise AssertionError(
                f"PLACE에서 예상 밖의 상태({fsm.state.name})로 넘어갔다")
    else:
        raise AssertionError("PLACE가 RETURN_HOME으로 끝나지 않았다")


def test_RETURN_HOME을_거쳐_결국_SEARCH_TARGET에_도착한다():
    """더 찾을 기물이 없어 RETURN_HOME에 들렀더라도, 결국 대기 상태인
    SEARCH_TARGET에 도착해야 한다(다음 기물이 화면에 나타나길 기다린다)."""
    sim = PiSim()
    fsm = MissionFSM()
    assert fsm.begin_carrying("rook")

    for n in range(1, MAX_STEPS + 1):
        fsm.step(sim.pose(), _NO_PIECE_LEFT, sim)
        if fsm.state == State.SEARCH_TARGET:
            break
    else:
        raise AssertionError(f"{MAX_STEPS} 사이클 안에 SEARCH_TARGET에 못 갔다 — "
                              f"상태 {fsm.state.name}")


def test_화면엔_없어도_대기중인_지시가_있으면_RETURN_HOME을_건너뛴다():
    """_next_target(화면상 다음 후보)이 없어도, 큐에 쌓인 사용자 지시가
    있으면 그 자체가 "다음에 할 일이 있다"는 뜻이다 — RETURN_HOME으로
    대기하러 갈 이유가 없다."""
    sim = PiSim()
    fsm = MissionFSM()
    assert fsm.begin_carrying("rook")

    # rook을 나르는 도중 새 지시(queen) — 손이 안 비었으니 큐에 쌓인다.
    # 이 시점 화면(_NO_PIECE_LEFT)에는 rook도 queen도 안 보인다(오버헤드
    # 사각지대 등으로 아직 안 잡혔다고 가정) — _next_target은 None이지만
    # 큐에는 지시가 남아 있다.
    applied = fsm.set_instruction("queen", dest_xy=mcfg.DELIVER_HERE_XY)
    assert applied is False
    assert fsm._queued_instruction_label == "queen"

    was_place = False
    for _ in range(MAX_STEPS):
        was_place = fsm.state == State.PLACE
        fsm.step(sim.pose(), _NO_PIECE_LEFT, sim)
        if was_place and fsm.state == State.SEARCH_TARGET:
            break
        if was_place and fsm.state == State.RETURN_HOME:
            raise AssertionError(
                "대기 중인 지시(queen)가 있는데도 RETURN_HOME을 거쳤다")
        if was_place and fsm.state not in (State.PLACE, State.NUDGE_BOX):
            raise AssertionError(
                f"PLACE에서 예상 밖의 상태({fsm.state.name})로 넘어갔다")
    else:
        raise AssertionError("PLACE가 SEARCH_TARGET으로 끝나지 않았다")

    assert fsm._instructed_label == "queen"
    assert fsm._queued_instruction_label is None


def test_RETURN_HOME_도착지는_DEFAULT_HOME_XY다():
    """다음 대기가 항상 같은 자리에서 시작된다는 것을 좌표로 고정한다."""
    sim = PiSim()
    fsm = MissionFSM()
    assert fsm.begin_carrying("rook")

    for _ in range(MAX_STEPS):
        fsm.step(sim.pose(), _NO_PIECE_LEFT, sim)
        if fsm.state == State.SEARCH_TARGET:
            break
    else:
        raise AssertionError("SEARCH_TARGET에 못 갔다")

    dist = ((sim.x - mcfg.DEFAULT_HOME_XY[0]) ** 2
            + (sim.y - mcfg.DEFAULT_HOME_XY[1]) ** 2) ** 0.5
    assert dist <= mcfg.HOME_ARRIVE_TOL_M
