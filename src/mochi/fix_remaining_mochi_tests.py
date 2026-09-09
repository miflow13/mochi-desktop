#!/usr/bin/env python3
from pathlib import Path
import json
import re

root = Path.cwd()
buddy_test = root / "tests" / "test_buddy.py"
sprite_test = root / "tests" / "test_sprites.py"
manifest = root / "assets" / "mochi" / "manifest.json"

for p in (buddy_test, sprite_test, manifest):
    if not p.exists():
        raise SystemExit(f"Missing {p}. Run this from the mochi-desktop repo root.")

text = buddy_test.read_text()

def replace_method(src: str, name: str, replacement: str) -> str:
    pattern = re.compile(
        rf"(?ms)^    def {re.escape(name)}\(self\).*?(?=^    def |^class |\Z)"
    )
    m = pattern.search(src)
    if not m:
        raise SystemExit(f"Could not find {name} in tests/test_buddy.py")
    return src[:m.start()] + replacement.rstrip() + "\n\n" + src[m.end():]

new_intro = '    def test_computer_emote_plays_single_animation(self) -> None:\n        buddy = SimpleNamespace(\n            state=SimpleNamespace(current=MochiState.IDLE),\n            _context_menu_open=False,\n            player=SimpleNamespace(animation=ANIMATIONS["idle"]),\n            _transition_to=Mock(return_value=True),\n            _computer_idle_source_id=None,\n            _play_animation=Mock(),\n        )\n\n        self.assertTrue(Buddy._start_computer_emote(buddy))\n\n        buddy._transition_to.assert_called_once_with(MochiState.COMPUTER)\n        buddy._play_animation.assert_called_once_with("computer", after="idle")'
new_cancel = '    def test_direct_input_cancels_computer_emote_and_returns_to_idle(self) -> None:\n        buddy = SimpleNamespace(\n            state=SimpleNamespace(current=MochiState.COMPUTER),\n            _transition_to=Mock(return_value=True),\n            _play_animation=Mock(),\n        )\n\n        self.assertTrue(Buddy._cancel_active_emote(buddy))\n\n        buddy._transition_to.assert_called_once_with(MochiState.IDLE)\n        buddy._play_animation.assert_called_once_with("idle")'

text = replace_method(
    text,
    "test_computer_intro_starts_one_owned_typing_timer",
    new_intro,
)
text = replace_method(
    text,
    "test_direct_input_cancels_computer_timer_and_returns_to_idle",
    new_cancel,
)
buddy_test.write_text(text)

data = json.loads(manifest.read_text())
animations = data.get("animations")
if not isinstance(animations, dict) or "heart" not in animations:
    raise SystemExit('Could not find animations["heart"] in assets/mochi/manifest.json')

heart = animations["heart"]
heart["fps"] = 1000.0 / 120.0
heart["loop"] = False
manifest.write_text(json.dumps(data, separators=(",", ":")) + "\n")

sprite_text = sprite_test.read_text()
pattern = re.compile(
    r'(def test_heart_is_a_single_manifest_backed_pass\(self\).*?'
    r'self\.assertEqual\(heart\.frame_duration_ms,\s*)\d+(\))',
    re.S,
)
sprite_text, n = pattern.subn(r'\g<1>120\2', sprite_text, count=1)
if n != 1:
    raise SystemExit("Could not update heart frame-duration assertion in tests/test_sprites.py")

sprite_test.write_text(sprite_text)

print("Patched:")
print("  tests/test_buddy.py")
print("  tests/test_sprites.py")
print("  assets/mochi/manifest.json")
print()
print("Now run:")
print("  python -m compileall -q src tests")
print("  pytest -q")
print("  git diff --check")
