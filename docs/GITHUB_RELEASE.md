# Publishing a GitHub source release (v0.1.2)

This source archive is v0.1.2 and is not published by these instructions. The
original source-release baseline was v0.1.1; do not reuse that version tag for
the updated code. Publishing requires permission to your GitHub account or
organization.

1. Review `README.md`, `LICENSE`, and `examples/data/README.md` (separate MIT / CC BY 4.0 licenses).
2. Run `python -m pip install -e '.[dev]'` and `python -m pytest -q` in a clean checkout.
3. For a new repository, initialize and push the source:

```bash
git init -b main
git add .
git commit -m "Release compwaffle v0.1.2"
gh auth login
gh repo create compwaffle --public --source=. --remote=origin --push
```

If the repository already exists, commit and push the changes to the existing
repository instead; do not recreate it. After the v0.1.2 commit is on your
branch, tag and publish that commit:

```bash
git tag v0.1.2
git push origin v0.1.2
gh release create v0.1.2 --title "compwaffle v0.1.2 — Hatch Tone Adjustment" \
  --notes "Category-aware hatch tones, with consistent Python in Excel support."
```

No PyPI publication is required. GitHub Actions checks run after pushes and pull requests.
