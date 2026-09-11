# Media and Music Detection

Mochi uses MPRIS playback metadata plus coarse browser-focus signals to decide whether ambient playback should trigger **WATCHING** or **DANCING**.

This page is the maintenance checklist for adding a new music website or debugging a site that Mochi classifies incorrectly.

## Priority model

Keep this behavior intact:

1. Explicit/watchable video → **WATCHING**
2. Confidently identified music → **DANCING**
3. Generic focused-browser playback → coarse **WATCHING** fallback
4. No media signal → normal ambient behavior

The generic browser fallback exists because Chromium can expose a playing MPRIS session without a useful URL or site name. Do **not** change generic browser playback to music; that would make podcasts, Twitch, web video, and other ambiguous playback trigger dancing.

`src/mochi/presence/music_dance.py` already allows confident music detection to replace only the coarse browser-watching fallback. Explicit YouTube/video detection still has priority.

## When a music website is treated as WATCHING

The usual cause is that the browser is playing media, but `src/mochi/music_activity.py` does not recognize the service as music.

Check what MPRIS exposes while the site is playing:

```bash
playerctl -l
playerctl -a status
playerctl -a metadata xesam:url
playerctl -a metadata xesam:title
```

If the URL identifies the service, prefer host-based detection. If Chromium omits the URL but consistently includes the service name in the media title, add a narrow title fallback too.

## Adding a known music website

### 1. Add its host

Edit `src/mochi/music_activity.py` and add the canonical domain to `_MUSIC_WEB_HOSTS`:

```python
_MUSIC_WEB_HOSTS = (
    "open.spotify.com",
    "soundcloud.com",
    # ...
    "examplemusic.com",
)
```

Host matching already accepts subdomains, so adding `examplemusic.com` also covers `www.examplemusic.com`.

### 2. Add a title fallback only when needed

If the browser often omits `xesam:url`, add a narrow service-name check in `_metadata_indicates_music()`:

```python
for value in _string_values(metadata.get("xesam:title")):
    lowered = value.strip().lower()
    if (
        "youtube music" in lowered
        or "examplemusic" in lowered
        or _looks_like_audio_file(value)
    ):
        return True
```

Only use a title marker that is strongly associated with the service. Avoid broad words such as `music`, `focus`, `radio`, or `playlist` because normal videos and podcasts can contain them.

### 3. Add regression tests

Update `tests/test_music_activity.py` with at least:

- browser + service URL + `Playing` → music
- browser + service title with missing URL → music, if a title fallback was added
- generic browser playback → still not music
- ordinary YouTube video → still not music

When practical, also test that paused playback is not treated as active music.

### 4. Run the focused tests

```bash
pytest -q tests/test_music_activity.py
```

Then run the full suite before merging:

```bash
pytest -q
```

## Brain.fm example

Brain.fm was originally treated as WATCHING because it was not in the known browser-music host list. Chromium playback therefore fell through to Mochi's generic focused-browser media fallback.

The fix was intentionally narrow:

- add `brain.fm` to `_MUSIC_WEB_HOSTS`
- recognize `brain.fm` in a browser media title when the URL is absent
- add URL and sparse-metadata regression tests

This lets Brain.fm trigger **DANCING** without weakening Mochi's conservative handling of unknown browser media.

## Files involved

- `src/mochi/music_activity.py` — music classification
- `src/mochi/media_activity.py` — watchable-video and focused-browser fallback classification
- `src/mochi/presence/music_dance.py` — WATCHING/DANCING priority and state behavior
- `tests/test_music_activity.py` — music classifier regressions
- `tests/test_media_activity.py` — video/browser media regressions

## Rule of thumb

**Be specific when promoting a source to music. Keep the ambiguous browser fallback ambiguous.**

That protects Mochi from fixing one streaming service while accidentally making every playing browser tab dance.