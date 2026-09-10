"""Small interaction defaults kept together for quick hands-on tuning."""

from __future__ import annotations

from dataclasses import dataclass

# Pointer movement required before a primary press becomes a drag. Keep this
# above normal click jitter while allowing a light, intentional pull.
DRAG_START_DISTANCE_PX = 4.0

# Drag-pose thresholds use filtered horizontal velocity normalized to 0..1.
# Full intensity remains deliberately quick at 700 px/s.
DRAG_SOFT_ENTER_THRESHOLD = 0.12
DRAG_MEDIUM_ENTER_THRESHOLD = 0.28
DRAG_MEDIUM_EXIT_THRESHOLD = 0.22
DRAG_HEAVY_VELOCITY_PX_PER_SECOND = 700.0
DRAG_VELOCITY_SMOOTHING = 0.28
DRAG_STATE_DWELL_MS = 0

# Animation timing is in milliseconds per frame and intentionally overrides
# authored manifest FPS at runtime. Pickup is much quicker than suspended drag.
PICKUP_FRAME_DURATION_MS = 25
DRAG_FRAME_DURATION_MS = 167
DRAG_SETTLE_DIRECTIONAL_MS = 70
DRAG_SETTLE_NEUTRAL_MS = 140
DRAG_VISUAL_IDLE_DELAY_SECONDS = 0.08
DRAG_BODY_SWAY_PX = 14

# Held-neutral handoff. Wait briefly before entering the authored sway loop so
# decaying drag velocity cannot bounce between a directional pose and sway.
# Once sway is active, tiny pointer jitter is ignored until the user makes a
# deliberate horizontal movement (~126 px/s with the default 700 px/s scale).
DRAG_SWAY_ENTER_DELAY_SECONDS = 0.10
DRAG_SWAY_EXIT_INTENSITY = 0.18

# Hover only fires on pointer entry. This cooldown absorbs rapid edge skims.
HOVER_HEART_COOLDOWN_SECONDS = 2.0

# The computer emote gets one owned idle timer and an independently owned
# typing-loop timer. Direct interaction cancels both safely.
COMPUTER_IDLE_DELAY_SECONDS = (45, 120)
COMPUTER_TYPING_DURATION_SECONDS = (3.0, 4.0)


@dataclass
class InteractionTuning:
    """Per-buddy mutable values exposed by the developer context menu."""

    drag_start_distance_px: float = DRAG_START_DISTANCE_PX
    drag_soft_enter_threshold: float = DRAG_SOFT_ENTER_THRESHOLD
    drag_medium_enter_threshold: float = DRAG_MEDIUM_ENTER_THRESHOLD
    drag_medium_exit_threshold: float = DRAG_MEDIUM_EXIT_THRESHOLD
    drag_heavy_velocity_px_per_second: float = DRAG_HEAVY_VELOCITY_PX_PER_SECOND
    drag_state_dwell_ms: int = DRAG_STATE_DWELL_MS
    hover_heart_cooldown_seconds: float = HOVER_HEART_COOLDOWN_SECONDS
    pickup_frame_duration_ms: int = PICKUP_FRAME_DURATION_MS
