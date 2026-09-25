# Contributing to Mochi

Thanks for helping Mochi grow. Keep changes small, explain the behavior being changed, and protect existing interactions from regressions.

## Workflow

1. Branch from the latest `main`.
2. Keep one focused concern per branch and pull request.
3. Add or update tests when behavior changes.
4. Update the nearest relevant documentation when public behavior, setup, or architecture changes.
5. Add notable user-facing changes to `CHANGELOG.md` when appropriate.
6. Run the full test suite before requesting review.
7. For interaction, animation, input, state, or windowing changes, also work through `REGRESSION_WATCHLIST.md` and verify live on the relevant Linux desktop environment.

## Art and animation contributions

Artists do not need to implement Python behavior to contribute an animation. Start with the [Mochi Artist Kit](artist-kit/README.md), use the canonical master and runtime animation library as references, and include the original transparent PNG frames or spritesheet plus the intended timing/loop information.

Runtime integration can be handled separately. Artwork accepted into the production library must still follow the asset rules in [assets/mochi/README.md](assets/mochi/README.md).

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

## Documentation

The root `README.md` is the project front door. Detailed architecture, testing, troubleshooting, and design notes belong under `docs/` so the README stays easy to scan.

Start with [`docs/README.md`](docs/README.md) to find the appropriate guide.

Documentation should describe behavior that exists or clearly label planned behavior as planned. Avoid duplicating the same implementation detail across several files when one canonical document can be linked instead.

## Before opening a pull request

```bash
python3 -m pytest -q
git diff --check
```

For GTK/XWayland behavior, unit tests are not enough. Verify the affected interaction live before merging.

The pull request description should state what changed, what is intentionally out of scope, how the change was verified, and any environment-specific limitations that still need testing.

## AI-assisted development

AI coding tools may be used for implementation, investigation, review, debugging, refactoring, and test generation. Contributors remain responsible for understanding the change, reviewing generated code, testing it, and describing its behavior accurately.

AI assistance does not replace the project's normal requirements for focused scope, regression testing, live Linux verification where relevant, or maintainer review.
