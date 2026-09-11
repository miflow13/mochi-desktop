"""Keep release metadata and runtime asset installation paths consistent."""

from pathlib import Path
import tomllib

from mochi import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_public_version_matches_distribution_metadata() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert __version__ == project["project"]["version"]


def test_every_runtime_asset_is_packaged_at_its_loader_path() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    installed = {}
    for destination, patterns in project["tool"]["setuptools"]["data-files"].items():
        for pattern in patterns:
            for source in ROOT.glob(pattern):
                target = Path(destination) / source.name
                assert target not in installed, f"Duplicate installed asset: {target}"
                installed[target] = source

    artwork = ROOT / "assets" / "mochi"
    expected = {
        Path("share/mochi") / source.relative_to(artwork): source
        for source in artwork.rglob("*.png")
    }
    expected[Path("share/mochi/manifest.json")] = artwork / "manifest.json"
    expected.update({
        Path("share/mochi/audio") / source.name: source
        for source in (ROOT / "assets" / "audio").glob("*.ogg")
    })
    for target, source in expected.items():
        assert installed.get(target) == source, f"Unpackaged runtime asset: {source}"
