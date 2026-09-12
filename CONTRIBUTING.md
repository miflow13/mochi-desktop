# Contributing to Mochi

Thanks for helping Mochi grow. Keep changes small, explain the behavior being changed, and protect existing interactions from regressions.

## Workflow

1. Branch from the latest `main`.
2. Keep one focused concern per branch and pull request.
3. Add or update tests when behavior changes.
4. Run the full test suite before requesting review.
5. For interaction, animation, input, state, or windowing changes, also work through `REGRESSION_WATCHLIST.md` and verify live on the relevant Linux desktop environment.

## Commit style

Use short, descriptive conventional prefixes:

- `feat:` new user-facing behavior
- `fix:` bug fixes
- `test:` test-only changes
- `docs:` documentation
- `ci:` automation and workflow changes
- `chore:` repository maintenance
- `refactor:` behavior-preserving structural changes

Prefer commits that explain the intent, not just the files touched.

## Before opening a pull request

```bash
python3 -m pytest -q
git diff --check
```

For GTK/XWayland behavior, unit tests are not enough. Verify the affected interaction live before merging.

## AI-assisted development

AI coding tools may be used for implementation, investigation, review, and debugging. Contributors remain responsible for understanding the change, reviewing generated code, testing it, and describing its behavior accurately.
