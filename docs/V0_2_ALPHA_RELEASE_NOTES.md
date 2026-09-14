# Mochi v0.2.0-alpha.1

Draft for a future **prerelease**; no tag or release has been created by this work.

This v0.2 alpha candidate hardens Mochi's existing desktop companion behavior.
Damaged or unavailable settings now recover safely, and shutdown explicitly
releases core timers, awareness monitors, menus and speech surfaces. Package and
runtime versions agree, and the interaction guide matches the current controls.

Existing v0.2 behavior includes idle animation, click reactions, pickup/drag/drop,
sleep/wake, typing and contextual media reactions, Stay Put and Edge Roam.
Care, feeding and progression development is paused and is not included here.

Fedora GNOME Wayland, using XWayland for Mochi's window, remains the primary target.
After first installation, log out and back in once to load the GNOME helper.
See the [installation guide](../README.md#install).

Known limitations: intermittent workspace freeze #45 remains under investigation;
mixed-scale/multi-monitor setups need more testing; Niri is experimental; optional
awareness and audio capabilities can be unavailable. Report the exact sequence,
desktop/session and monitor setup along with relevant `mochi --debug` output.

Publish only after the QA gates in [the readiness audit](V0_2_ALPHA_READINESS.md)
are signed off. The intended tag is `v0.2.0-alpha.1`; Python reports `0.2.0a1`.
