# anime-renamer

Rename/move torrent anime files into a Jellyfin-friendly folder + filename structure. 

## Features

- Scans an **inbox** folder for media files (by extension) and plans a destination path. 
- Can either **preview** actions (`scan`) or **perform** them (`apply`). 
- Writes a move **log** (`run-log.jsonl`) and status outputs (`status.json` / `status.csv`) when applying changes. 
- Supports **rollback** from the log file. 

## Requirements

- Python >= 3.10. 
- Dependencies are managed via `pyproject.toml` (Typer + PyYAML). 

## Install

From the repo root:

``python -m pip install -U. ``

``python -m pip install -e. ``

This installs the console command:

- `anime-renamer` 

## Quick start

1) Copy `config.yaml` to the repo root (or edit the existing one).  
2) Run a preview:

``anime-renamer scan --config config.yaml``

3) Apply the moves:

``anime-renamer apply --config config.yaml``

If anything goes wrong, rollback using the log:

``anime-renamer rollback --log run-log.jsonl``


## Commands

### Help

``anime-renamer --help``

### `scan` (preview)

Prints planned operations to the console (does **not** move files). 

``anime-renamer scan --config config.yaml``

### `apply` (do the moves)

Moves files and writes a move log + status files. 

Default outputs:  
- Log: `run-log.jsonl`   
- Status: `status.json` and `status.csv` 

``anime-renamer apply --config config.yaml``

Custom paths:

``anime-renamer apply --config config.yaml --log run-log.jsonl --status status --cleanup-empty true``

Flags:
- `--config`: Path to config file (default `config.yaml`). 
- `--log`: JSONL move log output path (default `run-log.jsonl`). 
- `--status`: Base path used to create `*.json` and `*.csv` (default `status`). 
- `--cleanup-empty`: Delete empty folders left in inbox after moving (default `true`). 

### `rollback` (undo moves)

Reverts moves based on the JSONL log. 

``anime-renamer rollback --log run-log.jsonl``

## Config

The CLI reads YAML config via `load_config()` (see `config.py`) using these top-level sections:

- `paths`: inbox/destination/quarantine paths.
- `rules`: allowed extensions, default season, extras mapping, etc.
- `series`: per-series overrides.
- `perplexity`: optional AI classification settings.

(Keep API keys out of git — use environment variables or local-only secrets.)

## Development

Run without installing (module mode):

``python -m anime_renamer.cli --help``

``python -m anime_renamer.cli scan --config config.yaml``

``python -m anime_renamer.cli apply --config config.yaml``

``python -m anime_renamer.cli rollback --log run-log.jsonl``
