---
name: Bug report
about: Report a Mochi alpha bug with reproduction steps and Linux environment details
title: ''
labels: ''
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Check existing issues first, especially #45 (Overview/workspace freeze) and
#68 (drag-direction latency). Both remain under investigation.

List the shortest sequence that reproduces the problem, starting from launch.
Mention any dragging, menu use, emote, sleep/wake, Overview, or workspace switch.

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Actual behavior**
What happened? Does it happen every time or intermittently?

**Linux environment**

- Distribution and version:
- Desktop environment/compositor and version:
- Session type (Wayland or X11):
- Monitor layout and scale factors:
- GNOME helper state, if applicable (`gnome-extensions info mochi-typing@miflow13`):

**Build and launch**

- Release tag or checkout branch and commit (`git branch --show-current`, `git rev-parse --short HEAD`):
- Install method and launch method (app grid, `mochi`, or source command):
- After updating, did you rerun `./install.sh` and quit/relaunch Mochi?

**Debug output**
Quit Mochi, run `mochi --debug`, and include relevant terminal output or a
traceback if available. Review logs/screenshots for personal information before posting.

**Additional context**
Add any other context about the problem here.
