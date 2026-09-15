"""Keep music awareness active while automatic dancing is temporarily disabled.

The existing MusicDanceMixin still owns MPRIS detection, media-priority handling,
and the developer-only Dance preview. This small layer suppresses only automatic
dance entry/resume during normal playback so Now Playing can ship independently.
"""

from mochi.state import MochiState

from .music_dance import MusicDanceMixin


class MusicAwarenessMixin(MusicDanceMixin):
    """Recognize music without automatically entering the DANCING state."""

    def _on_music_started(self) -> None:
        """Keep music-specific classification without starting the dance emote."""
        self._on_user_active()

        # Confident music detection should still replace only the intentionally
        # coarse focused-browser WATCHING fallback. Explicit video remains
        # untouched, matching the established media-priority behavior.
        if (
            self.state.current is MochiState.WATCHING
            and self._generic_browser_watch_active()
        ):
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")

        self._logger.debug("Music detected; automatic dance is disabled")

    def _maybe_resume_dancing(self) -> bool:
        """Do not resume automatic dancing after another interaction ends."""
        return False
