from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "pet.toml"


def _load_manifest() -> dict:
    return tomllib.loads(MANIFEST.read_text(encoding="utf-8"))


def _durations(data: dict, animation_name: str) -> list[int]:
    return [
        frame["duration_ms"]
        for frame in data["animations"][animation_name]["frames"]
    ]


def test_deskling_manifest_references_existing_assets() -> None:
    data = _load_manifest()

    assert data["schema_version"] == 1
    assert data["pet"]["name"] == "Mochi"

    animations = data["animations"]
    assert "idle" in animations
    assert "walk" in animations
    assert "walk_left" in animations
    assert "squish" in animations
    assert "heart" in animations

    referenced_files: list[Path] = []
    for animation in animations.values():
        assert animation["mode"] in {"once", "loop", "pingpong"}
        assert animation["frames"]
        for frame in animation["frames"]:
            assert frame["duration_ms"] > 0
            relative = Path(frame["file"])
            assert not relative.is_absolute()
            assert ".." not in relative.parts
            referenced_files.append(relative)

    missing = [path for path in referenced_files if not (ROOT / path).is_file()]
    assert missing == []


def test_deskling_behavior_targets_defined_animations() -> None:
    data = _load_manifest()
    animations = set(data["animations"])

    interaction = data["interaction"]
    assert interaction["click_animation"] in animations
    assert interaction["double_click_animation"] in animations

    for action in data["behavior"]["idle"]["actions"]:
        assert action["name"] in animations

    roam = data["behavior"]["roam"]
    assert roam["left_animation"] in animations
    assert roam["right_animation"] in animations


def test_deskling_preserves_authored_animation_timing() -> None:
    data = _load_manifest()

    expected = {
        "idle": [750, 500, 350, 900, 400, 1000],
        "blink": [50, 55, 65, 85, 65, 55, 50],
        "bounce": [50, 75, 85, 95, 135, 145, 110],
        "squish": [45, 70, 105, 120, 145, 125],
        "sleep": [90, 100, 120, 140, 160, 180],
        "wake": [70, 80, 90, 100, 100, 90],
    }

    for animation_name, durations in expected.items():
        assert _durations(data, animation_name) == durations
