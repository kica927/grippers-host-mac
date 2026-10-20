"""카메라 열기 — 초점 고정 순서만 본다(실물 카메라 없이)."""
import cv2

from localization import cameras


class FakeCap:
    """set/read 호출 순서를 기록하는 가짜 VideoCapture."""

    def __init__(self, *_args):
        self.log = []
        self.props = {cv2.CAP_PROP_FRAME_WIDTH: 1280, cv2.CAP_PROP_FRAME_HEIGHT: 720}

    def set(self, prop, value):
        self.log.append(("set", prop, value))
        self.props[prop] = value
        return True

    def get(self, prop):
        return self.props.get(prop, 0)

    def read(self):
        self.log.append(("read",))
        return True, None

    def isOpened(self):
        return True


def _open(monkeypatch, focus):
    made = []

    def factory(*args):
        made.append(FakeCap(*args))
        return made[-1]

    monkeypatch.setattr(cameras.cv2, "VideoCapture", factory)
    cameras.open_cams([0], 1280, 720, focus)
    return made[0].log


def test_focus_is_locked_after_autofocus_off_and_again_after_first_frame(monkeypatch):
    log = _open(monkeypatch, 0)
    af = [k for k, e in enumerate(log) if e[:2] == ("set", cv2.CAP_PROP_AUTOFOCUS)]
    fo = [k for k, e in enumerate(log) if e[:2] == ("set", cv2.CAP_PROP_FOCUS)]
    first_read = log.index(("read",))
    # 두 번 건다: 스트림 전 한 번, 첫 프레임 뒤 한 번
    assert len(af) == 2 and len(fo) == 2
    assert fo[0] < first_read < fo[1]
    # 매번 오토포커스를 먼저 끈 뒤 초점값을 넣는다(반대면 재초점이 덮어쓴다)
    assert af[0] < fo[0] and af[1] < fo[1]
    assert all(log[k][2] == 0 for k in fo)


def test_negative_focus_only_turns_autofocus_off(monkeypatch):
    log = _open(monkeypatch, -1)
    assert any(e[:2] == ("set", cv2.CAP_PROP_AUTOFOCUS) for e in log)
    assert not any(e[:2] == ("set", cv2.CAP_PROP_FOCUS) for e in log)


def test_focus_is_per_camera(monkeypatch):
    """팀이 쓰던 값 {0: 5, 1: 0} — 카메라마다 다른 값이 들어가야 한다."""
    made = []

    def factory(*args):
        made.append(FakeCap(*args))
        return made[-1]

    monkeypatch.setattr(cameras.cv2, "VideoCapture", factory)
    cameras.open_cams([0, 1, 2], 1280, 720, {0: 5, 1: 0})
    written = [[e[2] for e in cap.log if e[:2] == ("set", cv2.CAP_PROP_FOCUS)] for cap in made]
    assert written == [[5, 5], [0, 0], []]          # 표에 없는 2번은 오토포커스만 끈다


def test_parse_focus():
    assert cameras.parse_focus(None) is None
    assert cameras.parse_focus("5") == 5
    assert cameras.parse_focus("0=5,1=0") == {0: 5, 1: 0}


def test_config_default_matches_the_team_values(cfg):
    assert cfg.cameras.focus == {0: 5, 1: 0}


def test_backend_per_platform(monkeypatch):
    """DSHOW 는 Windows 전용 — 맥에서 쓰면 예외 없이 isOpened() 만 False 다."""
    monkeypatch.setattr(cameras.sys, "platform", "win32")
    assert cameras.capture_backend() == cv2.CAP_DSHOW
    monkeypatch.setattr(cameras.sys, "platform", "darwin")
    monkeypatch.setattr(cameras, "IS_MACOS", True)
    assert cameras.capture_backend() == cv2.CAP_AVFOUNDATION


class RefusingCap(FakeCap):
    """AVFoundation 처럼 초점 속성을 받지 않는(set -> False) 가짜."""

    def set(self, prop, value):
        super().set(prop, value)
        return prop not in (cv2.CAP_PROP_AUTOFOCUS, cv2.CAP_PROP_FOCUS)


def test_mac_says_focus_cannot_be_locked(monkeypatch, capsys):
    monkeypatch.setattr(cameras, "IS_MACOS", True)
    monkeypatch.setattr(cameras.cv2, "VideoCapture", RefusingCap)
    cameras.open_cams([0], 1280, 720, {0: 5})
    out = capsys.readouterr().out
    assert "초점 고정을 받지 않습니다" in out
    assert "로 읽힌다" not in out               # 되읽기 판정의 엉뚱한 말이 아니라 원인을 말한다


def test_mac_unopened_camera_mentions_permission(monkeypatch, capsys):
    class Closed(FakeCap):
        def isOpened(self):
            return False

    monkeypatch.setattr(cameras, "IS_MACOS", True)
    monkeypatch.setattr(cameras.cv2, "VideoCapture", Closed)
    cameras.open_cams([0], 1280, 720, None)
    assert "카메라 권한" in capsys.readouterr().out
