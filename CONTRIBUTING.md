# Contributing to ha-eufy-sdk

Thanks for helping out! This guide covers **how we branch and merge** so your PR lands smoothly.

## Branch model — target `dev`, not `main`

We use two long-lived branches:

- **`dev`** — the integration branch. **All contributions go here.**
- **`main`** — release-only. It's what HACS installs from when we tag a release.

```
your branch  ──►  PR into `dev`  ──►  maintainer review + green CI  ──►  merged to dev
                                                                            │
                              (when a release is ready) maintainers open    ▼
                              a  dev ─► main  PR, merge it, then tag ──►  HACS release
```

So the flow for a contribution is:

1. Fork (or, if you're a maintainer, branch the repo).
2. **Create your branch from `dev`.**
3. Make your change, keep it focused, update docs if behaviour changes.
4. **Open your pull request against `dev`.** PRs opened against `main` will be asked to retarget.
5. A maintainer reviews and merges.

> **Please don't open PRs into `main`.** `main` moves only when the maintainers cut a release by
> merging `dev → main` and tagging it. Both `main` and `dev` are protected — everything lands via PR.

## Who can merge

- **Maintainers** (repo owners) can merge PRs and cut releases.
- **Everyone else**: your PR needs an approving review from a maintainer before it can merge. CI must
  be green.

## Before you push — run the same checks CI does

Two workflows gate every PR into `main`/`dev` and must pass:

- **Lint** (`.github/workflows/lint.yml`) — [ruff](https://docs.astral.sh/ruff/):
  ```bash
  python3 -m ruff check .
  python3 -m ruff format . --check
  ```
  Fix everything automatically with the helper script:
  ```bash
  scripts/lint      # runs `ruff format .` then `ruff check . --fix`
  ```
- **Validate** (`.github/workflows/validate.yml`) — Home Assistant **hassfest** + **HACS** action.
  These run in CI; you don't need them locally.

## Testing your change in Home Assistant

This integration is a **client of the [bridge](https://github.com/RazzleDazzleBazzle/ha-eufy-sdk-bridge)** — it
needs a running bridge to do anything. Run one (Docker/add-on), install this integration into a test
HA instance via HACS **Custom repositories**, and point the config flow at your bridge.

## Reporting bugs

Open an [issue](../../issues/new/choose) with a clear summary, steps to reproduce, what you expected
vs. what happened, your HA version, and relevant logs (enable debug logging for `custom_components.eufy_sdk`).

## License

By contributing, you agree that your contributions are licensed under the project's
[MIT License](./LICENSE).
