from __future__ import annotations

import csv
import json
from pathlib import Path

import typer

from .config import load_config
from .executor import apply_operations, rollback_from_log, write_log_jsonl, delete_empty_dirs
from .parse import make_decision
from .planner import make_operation
from .scanner import list_media_files

app = typer.Typer(add_completion=False)


def _write_status_files(base: Path, rows: list[dict]) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)

    # JSON
    base.with_suffix(".json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # CSV
    csv_path = base.with_suffix(".csv")
    fieldnames = ["src", "dst", "decision_kind", "status"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


@app.command()
def scan(config: Path = typer.Option(Path("config.yaml"), exists=True)) -> None:
    cfg = load_config(config)
    media = list_media_files(cfg)

    typer.echo(f"Found {len(media)} media files.")
    if not media:
        typer.echo("No media files found. Check paths.inbox_dir and rules.allowed_ext.")
        return

    for m in media:
        dec = make_decision(m.path, cfg)
        op = make_operation(dec, cfg, m.path)
        typer.echo(f"[{dec.kind}] {op.src} -> {op.dst}")


@app.command()
def apply(
    config: Path = typer.Option(Path("config.yaml"), exists=True),
    log: Path = typer.Option(Path("run-log.jsonl")),
    status: Path = typer.Option(Path("status"), help="Base path for status.json/status.csv"),
    cleanup_empty: bool = typer.Option(True, help="Delete empty folders in inbox after moving"),
) -> None:
    cfg = load_config(config)
    media = list_media_files(cfg)

    typer.echo(f"Found {len(media)} media files.")
    if not media:
        typer.echo("No media files found. Nothing to apply.")
        return

    ops = []
    planned_rows: list[dict] = []

    for m in media:
        dec = make_decision(m.path, cfg)
        op = make_operation(dec, cfg, m.path)
        ops.append(op)
        planned_rows.append(
            {
                "src": str(op.src),
                "dst": str(op.dst),
                "decision_kind": dec.kind,
                "status": "PLANNED",
            }
        )

    # Execute moves + write move log
    records = apply_operations(ops, dry_run=False)
    write_log_jsonl(log, records)
    typer.echo(f"Wrote log: {log}")

    # Build status: moved vs quarantined (based on final destination path)
    quarantine_root = str(cfg.quarantine_dir.resolve()).lower()
    moved = 0
    quarantined = 0
    quarantined_files: list[str] = []

    moved_map = {r["src"]: r["dst"] for r in records}

    for row in planned_rows:
        final_dst = moved_map.get(row["src"], row["dst"])
        row["dst"] = final_dst
        row["status"] = "MOVED"
        moved += 1

        if str(Path(final_dst).resolve()).lower().startswith(quarantine_root):
            quarantined += 1
            quarantined_files.append(Path(final_dst).name)
            row["status"] = "QUARANTINED"

    _write_status_files(status, planned_rows)

    typer.echo(f"Moved: {moved}")
    typer.echo(f"Quarantined: {quarantined}")
    typer.echo(f"Wrote status: {status.with_suffix('.json')} and {status.with_suffix('.csv')}")

    if quarantined_files:
        typer.echo("Quarantine files:")
        for name in quarantined_files:
            typer.echo(f"- {name}")

    if cleanup_empty:
        deleted = delete_empty_dirs(cfg.inbox_dir)
        typer.echo(f"Deleted empty inbox folders: {deleted}")


@app.command()
def rollback(log: Path = typer.Option(Path("run-log.jsonl"), exists=True)) -> None:
    rollback_from_log(log)
    typer.echo("Rollback complete.")


if __name__ == "__main__":
    app()
