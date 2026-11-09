# Publishing the initial GitHub release

The repository is **not yet pushed**. These steps require permission to publish to your GitHub account or organization.

1. Review `README.md`, `LICENSE`, and `examples/data/README.md` (separate MIT / CC BY 4.0 licenses).
2. Run `python -m pip install -e '.[dev]'` and `python -m pytest -q` in a clean checkout.
3. Create and push the repository and the **v0.1.1** initial release tag:

```bash
git init -b main
git add .
git commit -m "Initial public release v0.1.1"
gh auth login
gh repo create compwaffle --public --source=. --remote=origin --push
git tag v0.1.1
git push origin v0.1.1
gh release create v0.1.1 --title "compwaffle v0.1.1 — Initial Release" \
  --notes "Initial source release of rounded fractional-cell Matplotlib waffle charts."
```

No PyPI publication is required. GitHub Actions checks run after pushes and pull requests.
