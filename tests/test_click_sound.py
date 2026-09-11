import tempfile
from pathlib import Path

from mochi.sound import SoundEvent, SoundManager


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, float]] = []

    def play(self, path: Path, volume: float) -> None:
        self.calls.append((path, volume))


def test_click_chirp_uses_uploaded_asset_name():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        chirp = root / "mochi_chirp_01.ogg"
        chirp.touch()
        backend = FakeBackend()
        manager = SoundManager(volume=0.6, asset_root=root, backend=backend)

        assert manager.play(SoundEvent.CLICK) is True
        assert backend.calls == [(chirp, 0.6)]
