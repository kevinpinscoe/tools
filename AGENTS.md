# Repository Guidelines

## Project Structure & Module Organization

This repository is a collection of small automation utilities. Most top-level files are standalone shell or Python scripts such as `jsonfmt`, `find-in-ai.sh`, and `walk_thru_repo_looking_for_files_missing_from_README.py`.

The main structured project is [`rss-feed-generators/`](/home/kinscoe/tools/rss-feed-generators), which contains one subdirectory per feed source:

- `rss-feed-generators/pinboard-recent/`

Each generator is intentionally self-contained: one Python script, optional local notes (`README.md`, `CLAUDE.md`, `AGENTS.md`), and helper scripts like `resume.sh`.

## Build, Test, and Development Commands

There is no global build system or package manager. Use direct script execution.

```bash
python3 rss-feed-generators/pinboard-recent/pinboard-recent-generator.py /tmp/pinboard.xml
python3 -m py_compile rss-feed-generators/*/*.py
python3 -c "import xml.etree.ElementTree as ET; ET.parse('/tmp/pinboard.xml'); print('OK')"
```

Use the `/tmp` output path for local testing; the production default writes under `/var/www/html/feed/...` and may require elevated privileges outside the systemd service.

## Coding Style & Naming Conventions

Follow the existing style in each script:

- Python: 4-space indentation, standard library only unless a directory explicitly documents otherwise.
- Prefer small, single-purpose functions such as `fetch_*()`, `build_*()`, and `write_*()`.
- Keep generator directories and filenames aligned, for example `lobste.rs/lobste.rs-generator.py`.
- Shell scripts should stay POSIX-friendly unless Bash-specific behavior is required.

## Testing Guidelines

This repo does not use a formal test framework. For Python utilities, validate by:

- Running the script against a temp output file.
- Checking syntax with `python3 -m py_compile`.
- Verifying generated XML or JSON can be parsed cleanly.

When adding a new generator, include a documented smoke-test command in that directory’s `README.md`.

## Commit & Pull Request Guidelines

This repository was re-initialized with a fresh Git history. Keep commits short, imperative, and specific, for example: `Add pinboard recent RSS generator` or `Document RSS generator smoke tests`.

The default branch is `main`, and the expected remote is `git@github.com:kevinpinscoe/tools.git`.

Pull requests should include:

- A concise description of the script or behavior changed.
- Local verification steps you ran.
- Sample output path or example command.
- Operational notes if the change affects timers, systemd units, or `/var/www/html/feed/`.

## Operations & Configuration

See [`rss-feed-generators/RUNBOOK.md`](/home/kinscoe/tools/rss-feed-generators/RUNBOOK.md) for scheduler, timer, and logging details. Do not hardcode secrets into scripts; prefer environment variables or local machine configuration.
