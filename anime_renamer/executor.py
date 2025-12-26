from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable, List

from .planner import Operation


def _unique_destination(dst: Path) -> Path:
    if not dst.exists():
        return dst
    for i in range(1, 1000):
        cand = dst.with_name(dst.stem + f"__dup{i}" + dst.suffix)
        if not cand.exists():
            return cand
    raise RuntimeError(f"Too many name collisions for: {dst}")


def apply_operations(ops: Iterable[Operation], dry_run: bool) -> List[dict]:
    log: List[dict] = []
    for op in ops:
        dst = op.dst
        record = {"action": op.kind, "src": str(op.src), "dst": str(dst)}

        if dry_run:
            log.append(record)
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        final = _unique_destination(dst)
        record["dst"] = str(final)
        shutil.move(str(op.src), str(final))
        log.append(record)

    return log


def write_log_jsonl(log_path: Path, records: List[dict]) -> None:
    log_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )


def rollback_from_log(log_path: Path) -> None:
    lines = log_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(x) for x in lines if x.strip()]
    for r in reversed(records):
        src = Path(r["src"])
        dst = Path(r["dst"])
        if dst.exists():
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(src))


def delete_empty_dirs(root: Path) -> int:
    """
    Delete empty folders under root (bottom-up).
    Returns number of folders deleted.
    """
    root = root.resolve()
    deleted = 0
    # Walk bottom-up so children removed before parents
    for p in sorted(root.rglob("*"), reverse=True):
        if p.is_dir():
            try:
                next(p.iterdir())
            except StopIteration:
                # Empty dir
                p.rmdir()
                deleted += 1
    return deleted
