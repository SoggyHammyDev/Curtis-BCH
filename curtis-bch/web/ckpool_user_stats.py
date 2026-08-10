import json
import math
from pathlib import Path
from typing import Callable


def _aliases(configured_user: str) -> list[str]:
    raw = str(configured_user or "").strip()
    if not raw:
        return []
    values = [raw]
    if ":" in raw:
        prefixless = raw.split(":", 1)[1].strip()
        if prefixless:
            values.append(prefixless)
    return list(dict.fromkeys(values))


def _number(value: object) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _worker_key(workername: object, aliases: list[str]) -> str:
    raw = str(workername or "").strip()
    folded = raw.casefold()
    for alias in sorted(aliases, key=len, reverse=True):
        alias_folded = alias.casefold()
        if folded == alias_folded:
            return ""
        marker = alias_folded + "."
        if folded.startswith(marker):
            return folded[len(marker) :]
    return folded


def _merge(
    records: list[dict],
    aliases: list[str],
    parse_hashrate_ths: Callable[[object], float | None],
) -> dict:
    if not records:
        return {}
    if len(records) == 1:
        return dict(records[0])

    def lastshare(item: dict) -> float:
        return _number(item.get("lastshare")) or 0.0

    merged = dict(max(records, key=lastshare))
    hashrate_fields = (
        "hashrate1m",
        "hashrate5m",
        "hashrate1hr",
        "hashrate1d",
        "hashrate7d",
    )

    def merge_metrics(out: dict, items: list[dict]) -> None:
        for field in hashrate_fields:
            values = [parse_hashrate_ths(item.get(field)) for item in items]
            usable = [
                float(value)
                for value in values
                if value is not None and math.isfinite(float(value))
            ]
            if usable:
                out[field] = sum(usable)

        for field in ("shares", "authorised"):
            usable = [
                value
                for value in (_number(item.get(field)) for item in items)
                if value is not None
            ]
            if usable:
                total = sum(usable)
                out[field] = int(total) if float(total).is_integer() else total

        for field in ("bestshare", "bestever", "lastshare"):
            usable = [
                value
                for value in (_number(item.get(field)) for item in items)
                if value is not None
            ]
            if usable:
                value = max(usable)
                out[field] = int(value) if float(value).is_integer() else value

    merge_metrics(merged, records)

    groups: dict[str, list[dict]] = {}
    for record in records:
        rows = record.get("worker") if isinstance(record.get("worker"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("workername") or "").strip()
            key = _worker_key(name, aliases)
            if not key and not name:
                continue
            groups.setdefault(key, []).append(row)

    workers: list[dict] = []
    for rows in groups.values():
        worker = dict(max(rows, key=lastshare))
        merge_metrics(worker, rows)
        workers.append(worker)
    workers.sort(key=lastshare, reverse=True)
    merged["worker"] = workers

    counts = [
        max(0, int(value))
        for value in (_number(record.get("workers")) for record in records)
        if value is not None
    ]
    merged["workers"] = min(len(workers), sum(counts)) if counts else len(workers)
    return merged


def read_merged_user_stats(
    users_dir: Path,
    configured_user: str,
    parse_hashrate_ths: Callable[[object], float | None],
) -> dict:
    aliases = _aliases(configured_user)
    alias_keys = {alias.casefold() for alias in aliases}
    matches: list[tuple[float, dict]] = []
    fallback: list[tuple[float, dict]] = []

    try:
        candidates = list(users_dir.iterdir())
    except Exception:
        candidates = []

    for path in candidates:
        try:
            if not path.is_file():
                continue
            raw = path.read_text(encoding="utf-8", errors="replace").strip() or "{}"
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                continue
            item = (float(path.stat().st_mtime), obj)
            fallback.append(item)
            if path.name.casefold() in alias_keys:
                matches.append(item)
        except Exception:
            continue

    if matches:
        matches.sort(key=lambda item: item[0], reverse=True)
        return _merge(
            [item[1] for item in matches],
            aliases,
            parse_hashrate_ths,
        )
    if fallback:
        fallback.sort(key=lambda item: item[0], reverse=True)
        return fallback[0][1]
    return {}
