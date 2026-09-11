# Mochi maintenance tools

Runtime artwork lives in `assets/mochi/` and `assets/mochi/manifest.json` is the source of truth.

`export_animation_gifs.py` creates local GIF previews from the current runtime animation library. Generated previews belong in `animation-gifs/`, which is intentionally ignored by Git.

Install the development extras before running maintenance tools:

```bash
python -m pip install -e ".[dev]"
```

Historical programmatic sprite-authoring scripts and superseded source sets are preserved in Git history rather than kept in the alpha release tree. New production artwork should follow `assets/mochi/README.md` and preserve the handcrafted source art.
