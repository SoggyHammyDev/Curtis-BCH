import base64
import ast
import hashlib
import io
import json
import math
import os
import platform
import re
import socket
import threading
import time
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from ckpool_user_stats import read_merged_user_stats


_DEFAULT_STATIC_DIR = "/app/static" if Path("/app/static").exists() else "/data/ui/static"
STATIC_DIR = Path(os.getenv("STATIC_DIR", _DEFAULT_STATIC_DIR))
CKPOOL_STATUS_DIR = Path(os.getenv("CKPOOL_STATUS_DIR", "/data/pool/www/pool"))
CKPOOL_USERS_DIR = Path(os.getenv("CKPOOL_USERS_DIR", "/data/pool/www/users"))
CKPOOL_LOG_PATH = Path(os.getenv("CKPOOL_LOG_PATH", "/data/pool/www/ckpool.log"))
CKPOOL_SHARELOG_ROOT = Path(os.getenv("CKPOOL_SHARELOG_ROOT", "/data/pool/www"))
CKPOOL_CONF_PATH = Path(os.getenv("CKPOOL_CONF_PATH", "/data/pool/config/ckpool.conf"))
NODE_CONF_PATH = Path("/data/node/bitcoin.conf")
NODE_LOG_PATH = Path("/data/node/debug.log")
NODE_REINDEX_FLAG_PATH = Path("/data/node/.reindex-chainstate")
STATE_DIR = Path("/data/ui/state")
POOL_SERIES_PATH = STATE_DIR / "pool_timeseries.jsonl"
POOL_STATE_PATH = STATE_DIR / "pool_state.json"
ROUND_EFFORT_STATE_PATH = STATE_DIR / "round_effort_state.json"
CKPOOL_LOG_STATE_PATH = STATE_DIR / "ckpool_log_state.json"
BLOCKS_STATE_PATH = STATE_DIR / "blocks_state.json"
INSTALL_ID_PATH = STATE_DIR / "install_id.txt"
NODE_CACHE_PATH = STATE_DIR / "node_cache.json"
POOL_CACHE_PATH = STATE_DIR / "pool_cache.json"
POOL_WORKERS_CACHE_PATH = STATE_DIR / "pool_workers_cache.json"
CHECKIN_STATE_PATH = STATE_DIR / "checkin.json"
CKPOOL_FALLBACK_DONATION_ADDRESS = "14BMjogz69qe8hk9thyzbmR5pg34mVKB1e"

APP_CHANNEL = os.getenv("APP_CHANNEL", "").strip()
NETWORK_IP = os.getenv("NETWORK_IP", "").strip()
BCHN_IMAGE = os.getenv("BCHN_IMAGE", "").strip()
CKPOOL_IMAGE = os.getenv("CKPOOL_IMAGE", "").strip()
DEFAULT_SUPPORT_BASE_URL = "https://axebench.dreamnet.uk"
INSTALL_ID_HEADER = "X-Install-Id"

def _env_or_default(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    val = raw.strip()
    return val or default


SUPPORT_CHECKIN_URL = _env_or_default("SUPPORT_CHECKIN_URL", f"{DEFAULT_SUPPORT_BASE_URL}/api/telemetry/ping")
SUPPORT_TICKET_URL = _env_or_default("SUPPORT_TICKET_URL", f"{DEFAULT_SUPPORT_BASE_URL}/api/support/upload")

APP_ID = "curtis-bch"
APP_VERSION = os.getenv("APP_VERSION", "0.1.8").strip() or "0.1.8"
APP_VERSION_SUFFIX = os.getenv("APP_VERSION_SUFFIX", "").strip()
DISPLAY_VERSION = f"{APP_VERSION}{APP_VERSION_SUFFIX}"

BCH_RPC_HOST = os.getenv("BCH_RPC_HOST", "bchn")
BCH_RPC_PORT = int(os.getenv("BCH_RPC_PORT", "28332"))
BCH_RPC_USER = os.getenv("BCH_RPC_USER", "bch")
BCH_RPC_PASS = os.getenv("BCH_RPC_PASS", "")
CKPOOL_STRATUM_HOST = os.getenv("CKPOOL_STRATUM_HOST", "ckpool")
CKPOOL_STRATUM_PORT = int(os.getenv("CKPOOL_STRATUM_PORT", "3333"))

SAMPLE_INTERVAL_S = int(os.getenv("SERIES_SAMPLE_INTERVAL_S", "30"))
POOL_CACHE_REFRESH_S = float(os.getenv("POOL_CACHE_REFRESH_S", "15"))
POOL_CACHE_TTL_S = float(os.getenv("POOL_CACHE_TTL_S", "60"))
POOL_WORKERS_CACHE_REFRESH_S = float(os.getenv("POOL_WORKERS_CACHE_REFRESH_S", "15"))
POOL_WORKERS_CACHE_TTL_S = float(os.getenv("POOL_WORKERS_CACHE_TTL_S", "60"))
ACTIVE_WORKER_WINDOW_S = int(os.getenv("ACTIVE_WORKER_WINDOW_S", "300"))
STALE_WORKER_WINDOW_S = int(os.getenv("STALE_WORKER_WINDOW_S", "86400"))
BACKSCAN_DEFAULT_INTERVAL_S = int(os.getenv("BACKSCAN_INTERVAL_S", "15"))
BACKSCAN_DEFAULT_MAX_BLOCKS = int(os.getenv("BACKSCAN_MAX_BLOCKS", "10"))
BACKSCAN_MAX_BLOCKS_CAP = int(os.getenv("BACKSCAN_MAX_BLOCKS_CAP", "5000"))
MAX_RETENTION_S = int(os.getenv("SERIES_MAX_RETENTION_S", str(7 * 24 * 60 * 60)))
MAX_SERIES_POINTS = int(os.getenv("SERIES_MAX_POINTS", "20000"))

INSTALL_ID = None


PAYOUT_SCRIPT_CACHE: dict[str, str] = {}
PAYOUT_SCRIPT_CACHE_LOCK = threading.Lock()

_POOL_CACHE_LOCK = threading.Lock()
_POOL_CACHE: dict = {}

_POOL_WORKERS_CACHE_LOCK = threading.Lock()
_POOL_WORKERS_CACHE: dict = {}
_ROUND_EFFORT_UPDATE_LOCK = threading.Lock()

_CKPOOL_LOG_TIMESTAMP_RE = re.compile(r"^\[([^]]+)\]")
_CKPOOL_NETWORK_DIFF_RE = re.compile(r"Network diff set to ([0-9]+(?:\.[0-9]+)?)")
_CKPOOL_RUNTIME_RE = re.compile(r'Pool:\{"runtime":\s*([0-9]+)')
_CKPOOL_ACCEPTED_RE = re.compile(r'Pool:\{.*?"accepted":\s*([0-9]+)')


def _install_time_s() -> int:
    # Prefer the earliest timestamp we have locally (first time-series sample).
    try:
        if POOL_SERIES_PATH.exists() and POOL_SERIES_PATH.is_file():
            with POOL_SERIES_PATH.open("r", encoding="utf-8", errors="replace") as f:
                first = f.readline().strip()
            if first:
                obj = json.loads(first)
                t = obj.get("t") if isinstance(obj, dict) else None
                if t is not None:
                    t_i = int(float(t))
                    if t_i > 1_000_000_000_000:  # ms
                        return int(t_i / 1000)
                    if t_i > 1_000_000_000:  # s
                        return int(t_i)
    except Exception:
        pass
    try:
        if INSTALL_ID_PATH.exists():
            return int(INSTALL_ID_PATH.stat().st_mtime)
    except Exception:
        pass
    try:
        if STATE_DIR.exists():
            return int(STATE_DIR.stat().st_mtime)
    except Exception:
        pass
    return int(time.time())


def _record_payout_history(addr_legacy: str) -> None:
    a = (addr_legacy or "").strip()
    if not a:
        return
    try:
        state = _read_json_file(POOL_STATE_PATH)
    except Exception:
        state = {}

    items = state.get("payout_history") if isinstance(state.get("payout_history"), list) else []
    existing = {str(it.get("addr")) for it in items if isinstance(it, dict) and it.get("addr")}
    if a not in existing:
        items.append({"addr": a, "t": int(time.time())})

    # Keep last 20.
    items = [it for it in items if isinstance(it, dict) and it.get("addr")]
    items = items[-20:]
    state["payout_history"] = items

    if not isinstance(state.get("first_seen_at"), int):
        state["first_seen_at"] = _install_time_s()

    _write_json_file(POOL_STATE_PATH, state)


def _payout_history_addresses() -> list[str]:
    out: list[str] = []

    # Current address from ckpool config, if set.
    try:
        conf = _read_ckpool_conf()
        cur = str(conf.get("btcaddress") or "").strip()
        if cur and cur not in [CKPOOL_FALLBACK_DONATION_ADDRESS, "CHANGEME_BCH_PAYOUT_ADDRESS"]:
            out.append(cur)
    except Exception:
        pass

    try:
        state = _read_json_file(POOL_STATE_PATH)
        items = state.get("payout_history") if isinstance(state.get("payout_history"), list) else []
        for it in items:
            if not isinstance(it, dict):
                continue
            a = str(it.get("addr") or "").strip()
            if a:
                out.append(a)
    except Exception:
        pass

    # Dedupe preserving order (most recent last is fine).
    seen = set()
    uniq: list[str] = []
    for a in out:
        if a in seen:
            continue
        seen.add(a)
        uniq.append(a)
    return uniq


def _payout_scripts_hex(addrs: list[str]) -> set[str]:
    scripts: set[str] = set()
    for a in addrs:
        addr = (a or "").strip()
        if not addr:
            continue
        with PAYOUT_SCRIPT_CACHE_LOCK:
            cached = PAYOUT_SCRIPT_CACHE.get(addr)
        if cached:
            scripts.add(cached)
            continue
        try:
            res = _rpc_call("validateaddress", [addr]) or {}
            spk = str(res.get("scriptPubKey") or "").strip().lower()
            if spk:
                scripts.add(spk)
                with PAYOUT_SCRIPT_CACHE_LOCK:
                    PAYOUT_SCRIPT_CACHE[addr] = spk
        except Exception:
            continue
    return scripts


def _ckpool_user_best_share(addr: str) -> tuple[float | None, str | None]:
    """
    Read ckpool's per-user status file (named by address) and return:
    (best_share_difficulty, workername_for_best_share)
    """
    a = (addr or "").strip()
    if not a:
        return None, None
    try:
        base = CKPOOL_USERS_DIR.resolve()
    except Exception:
        base = CKPOOL_USERS_DIR
    path = (CKPOOL_USERS_DIR / a).resolve()
    try:
        if base and not str(path).startswith(str(base)):
            return None, None
        if not path.exists() or not path.is_file():
            return None, None
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
        if not raw:
            return None, None
        obj = _extract_json_obj(raw)
        if not isinstance(obj, dict):
            return None, None

        best = obj.get("bestshare") or obj.get("best_share") or obj.get("bestShare")
        try:
            best_f = float(best)
        except Exception:
            best_f = None
        if best_f is not None and not math.isfinite(best_f):
            best_f = None

        best_worker = None
        try:
            workers = obj.get("worker")
            if isinstance(workers, list):
                best_w = -1.0
                for w in workers:
                    if not isinstance(w, dict):
                        continue
                    v = w.get("bestshare") or w.get("best_share") or w.get("bestShare")
                    try:
                        v_f = float(v)
                    except Exception:
                        continue
                    if not math.isfinite(v_f):
                        continue
                    if v_f > best_w:
                        best_w = v_f
                        best_worker = str(w.get("workername") or "").strip() or None
                if best_f is None and best_w >= 0:
                    best_f = best_w
        except Exception:
            pass

        return best_f, best_worker
    except Exception:
        return None, None


def _reset_ckpool_bestshare(addrs: list[str]) -> dict:
    # Do NOT attempt to mutate ckpool's /www/users files: ckpool will overwrite them.
    # Instead, reset Curtis BCH's "best share since block" tracker and ignore the current all-time best share value.
    now_s = int(time.time())
    uniq: list[str] = []
    seen = set()
    for a in addrs:
        s = str(a or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        uniq.append(s)

    best = None
    best_worker = None
    for a in uniq:
        try:
            d, w = _ckpool_user_best_share(a)
            if d is None:
                continue
            d_i = _best_share_int(d)
            if d_i is None or d_i <= 0:
                continue
            if best is None or d_i > best:
                best = d_i
                best_worker = w
        except Exception:
            continue

    try:
        state = _read_json_file(POOL_STATE_PATH)
    except Exception:
        state = {}

    state["bestshare_reset_at"] = now_s
    _reset_since_block_best_share_tracker(
        pool_state=state,
        started_at=now_s,
        exclude_value=int(best) if best is not None else None,
        exclude_reason="manual",
        scan_from_start=False,
        anchor_hash=str(state.get("since_block_anchor_hash") or "").strip().lower() or None,
    )
    _write_json_file(POOL_STATE_PATH, state)
    _patch_bestshare_caches(reset_at=now_s)

    return {"ok": True, "t": now_s, "excludedValue": best, "excludedWorker": best_worker}


def _maybe_backscan_blocks(max_blocks: int = 10) -> None:
    # Incremental backscan that finds blocks mined by this pool's payout address(es).
    try:
        addrs = _payout_history_addresses()
        if not addrs:
            return
        addr_hash = hashlib.sha256("|".join(sorted(addrs)).encode("utf-8")).hexdigest()

        state = _read_json_file(BLOCKS_STATE_PATH)
        scan = state.get("backscan") if isinstance(state.get("backscan"), dict) else {}
        prev_hash = str(scan.get("payoutAddrHash") or "").strip().lower() or None
        now_s = int(time.time())

        if prev_hash and prev_hash != addr_hash:
            if bool(scan.get("complete")):
                scan["stale"] = True
                scan["enabled"] = False
                scan["payoutAddrHash"] = addr_hash
                scan["updatedAt"] = now_s
                state["backscan"] = scan
                _write_json_file(BLOCKS_STATE_PATH, state)
                return
            if not bool(scan.get("enabled")):
                scan["stale"] = True
                scan["enabled"] = False
                scan["payoutAddrHash"] = addr_hash
                scan["updatedAt"] = now_s
                state["backscan"] = scan
                _write_json_file(BLOCKS_STATE_PATH, state)
                return
            # Scan in progress and user likely changed payout address: restart pointers.
            scan = {}

        enabled = bool(scan.get("enabled", False))
        if bool(scan.get("complete")):
            return
        if not enabled:
            return

        scripts = _payout_scripts_hex(addrs)
        if not scripts:
            return

        events = state.get("events") if isinstance(state.get("events"), list) else []
        known = {e.get("hash") for e in events if isinstance(e, dict)}

        interval_s = int(scan.get("intervalS") or BACKSCAN_DEFAULT_INTERVAL_S)
        last_run = int(scan.get("lastRunAt") or 0)
        if interval_s > 0 and last_run and (now_s - last_run) < interval_s:
            return

        max_blocks = int(scan.get("maxBlocks") or max_blocks or BACKSCAN_DEFAULT_MAX_BLOCKS)
        next_h = scan.get("nextHeight")
        start_h = scan.get("startHeight")
        tip_h = _rpc_call("getblockcount")

        try:
            tip_h = int(tip_h)
        except Exception:
            return

        if next_h is None or start_h is None:
            install_t = _install_time_s()
            approx_blocks = max(0, int((now_s - int(install_t)) / 600))
            start_h = max(0, tip_h - approx_blocks - 10)
            next_h = int(start_h)
            scan = {
                "startHeight": int(start_h),
                "nextHeight": int(next_h),
                "tipHeightAtStart": int(tip_h),
                "startedAt": now_s,
                "updatedAt": now_s,
                "enabled": True,
                "complete": False,
                "payoutAddrHash": addr_hash,
            }

        blocks_done = 0
        while blocks_done < max_blocks and int(next_h) <= tip_h:
            h = int(next_h)
            next_h = h + 1
            blocks_done += 1

            try:
                blockhash = _rpc_call("getblockhash", [h])
                if not isinstance(blockhash, str) or not re.match(r"^[0-9a-fA-F]{64}$", blockhash):
                    continue
                bh = blockhash.lower()
                if bh in known:
                    continue

                # Use verbosity=2 so the coinbase transaction is included without requiring txindex
                # (getrawtransaction may fail when txindex=0).
                blk = _rpc_call("getblock", [bh, 2]) or {}
                if not isinstance(blk, dict):
                    continue
                txs = blk.get("tx")
                if not isinstance(txs, list) or not txs:
                    continue
                cb = txs[0]
                if not isinstance(cb, dict):
                    continue
                coinbase_txid = cb.get("txid") or cb.get("hash")
                if not isinstance(coinbase_txid, str) or not re.match(r"^[0-9a-fA-F]{64}$", coinbase_txid):
                    continue
                vouts = cb.get("vout")
                if not isinstance(vouts, list):
                    continue

                matched = False
                for v in vouts:
                    if not isinstance(v, dict):
                        continue
                    spk = v.get("scriptPubKey")
                    if not isinstance(spk, dict):
                        continue
                    spk_hex = str(spk.get("hex") or "").strip().lower()
                    if spk_hex and spk_hex in scripts:
                        matched = True
                        break

                if not matched:
                    continue

                net_diff = None
                try:
                    nd = blk.get("difficulty")
                    if nd is not None:
                        nd_f = float(nd)
                        if math.isfinite(nd_f) and nd_f > 0:
                            net_diff = nd_f
                except Exception:
                    net_diff = None

                solve_diff = None
                solve_worker = None
                try:
                    best = None
                    best_w = None
                    for a in addrs:
                        d, w = _ckpool_user_best_share(a)
                        if d is None:
                            continue
                        if best is None or d > best:
                            best = d
                            best_w = w
                    solve_diff = best
                    solve_worker = best_w
                except Exception:
                    solve_diff = None
                    solve_worker = None

                t = blk.get("time")
                try:
                    t_i = int(t) if t is not None else now_s
                except Exception:
                    t_i = now_s

                conf = blk.get("confirmations")
                try:
                    conf_i = int(conf) if conf is not None else None
                except Exception:
                    conf_i = None

                events.append(
                    {
                        "t": t_i,
                        "hash": bh,
                        "height": h,
                        "coinbase_txid": coinbase_txid.lower(),
                        "confirmations": conf_i,
                        "network_difficulty": net_diff,
                        "solve_diff": solve_diff,
                        "solve_worker": solve_worker,
                        "source": "backscan",
                    }
                )
                known.add(bh)
            except Exception:
                continue

        scan["nextHeight"] = int(next_h)
        scan["tipHeightLast"] = int(tip_h)
        scan["updatedAt"] = now_s
        scan["lastRunAt"] = now_s
        scan["complete"] = bool(int(next_h) > tip_h)
        scan["enabled"] = bool(scan.get("enabled", False))
        scan["payoutAddrHash"] = addr_hash
        if scan["complete"]:
            scan["enabled"] = False
            scan["completedAt"] = now_s

        state["backscan"] = scan
        state["events"] = events[-200:]
        _write_json_file(BLOCKS_STATE_PATH, state)
    except Exception:
        return


def _json(data, status=200):
    body = json.dumps(data).encode("utf-8")
    return status, body, "application/json; charset=utf-8"


def _parse_month_yyyy_mm(value: str | None) -> int | None:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m").replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


def _estimate_start_height(tip_h: int, from_ts: int, spacing_s: int, buffer_blocks: int) -> int:
    now_s = int(time.time())
    from_ts = int(from_ts)
    if from_ts <= 0 or from_ts >= now_s:
        return max(0, int(tip_h) - int(buffer_blocks))
    approx_blocks = max(0, int((now_s - from_ts) / max(1, int(spacing_s))))
    return max(0, int(tip_h) - approx_blocks - int(buffer_blocks))


def _read_static(rel_path: str):
    # Ignore query-string fragments (e.g. /app.js?v=... for cache-busting).
    rel = urlsplit(rel_path).path.lstrip("/") or "index.html"
    path = (STATIC_DIR / rel).resolve()
    if not str(path).startswith(str(STATIC_DIR.resolve())):
        return 403, b"forbidden", "text/plain; charset=utf-8"
    if not path.exists() or not path.is_file():
        return 404, b"not found", "text/plain; charset=utf-8"
    suffix = path.suffix.lower()
    content_type = "application/octet-stream"
    if suffix in [".html", ".htm"]:
        content_type = "text/html; charset=utf-8"
    elif suffix == ".css":
        content_type = "text/css; charset=utf-8"
    elif suffix == ".js":
        content_type = "application/javascript; charset=utf-8"
    elif suffix == ".svg":
        content_type = "image/svg+xml"
    elif suffix == ".png":
        content_type = "image/png"
    elif suffix == ".webp":
        content_type = "image/webp"

    if rel == "index.html" and content_type.startswith("text/html"):
        try:
            html = path.read_text(encoding="utf-8", errors="replace")
            html = html.replace("__APP_VERSION__", DISPLAY_VERSION)
            html = html.replace("__APP_CHANNEL__", APP_CHANNEL or "")
            return 200, html.encode("utf-8"), content_type
        except Exception:
            pass

    return 200, path.read_bytes(), content_type


def _rpc_call(method: str, params=None):
    if params is None:
        params = []
    url = f"http://{BCH_RPC_HOST}:{BCH_RPC_PORT}/"
    payload = json.dumps({"jsonrpc": "1.0", "id": "umbrel", "method": method, "params": params}).encode("utf-8")

    auth = base64.b64encode(f"{BCH_RPC_USER}:{BCH_RPC_PASS}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
        method="POST",
    )
    last_err = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            last_err = None
            break
        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(0.4)
                continue
            raise
    if last_err is not None:
        raise last_err
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data.get("result")


def _rpc_error_details(exc: Exception | str | None) -> tuple[int | None, str]:
    text = str(exc or "").strip()
    if not text:
        return None, ""

    code = None
    message = text
    try:
        obj = ast.literal_eval(text)
        if isinstance(obj, dict):
            raw_code = obj.get("code")
            try:
                code = int(raw_code) if raw_code is not None else None
            except Exception:
                code = None
            raw_message = obj.get("message")
            if raw_message is not None:
                message = str(raw_message).strip() or text
            return code, message
    except Exception:
        pass

    m = re.search(r"'code'\s*:\s*(-?\d+)", text)
    if m:
        try:
            code = int(m.group(1))
        except Exception:
            code = None
    m = re.search(r"'message'\s*:\s*'([^']+)'", text)
    if m:
        message = m.group(1).strip() or text
    return code, message


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def _write_text(path: Path, value: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.strip() + "\n", encoding="utf-8")


def _get_or_create_install_id() -> str:
    existing = _read_text(INSTALL_ID_PATH)
    if existing:
        return existing
    new_id = uuid.uuid4().hex
    _write_text(INSTALL_ID_PATH, new_id)
    return new_id


def _read_json(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, data: dict):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        pass


def _post_json(url: str, payload: dict, *, timeout_s: int = 6, headers: dict | None = None):
    body = json.dumps(payload).encode("utf-8")
    all_headers = {"Content-Type": "application/json"}
    if headers:
        all_headers.update(headers)
    req = urllib.request.Request(
        url,
        data=body,
        headers=all_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status, resp.read()
    except HTTPError as e:
        try:
            return int(getattr(e, "code", 0) or 0), e.read() or b""
        except Exception:
            return int(getattr(e, "code", 0) or 0), b""


def _encode_multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]):
    boundary = uuid.uuid4().hex
    crlf = "\r\n"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}{crlf}".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"{crlf}{crlf}'.encode("utf-8"))
        body.extend(value.encode("utf-8"))
        body.extend(crlf.encode("utf-8"))

    for name, (filename, data, content_type) in files.items():
        body.extend(f"--{boundary}{crlf}".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"{crlf}'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}{crlf}{crlf}".encode("utf-8"))
        body.extend(data)
        body.extend(crlf.encode("utf-8"))

    body.extend(f"--{boundary}--{crlf}".encode("utf-8"))
    return boundary, bytes(body)


def _post_support_bundle(url: str, *, bundle_bytes: bytes, filename: str, timeout_s: int = 20):
    boundary, body = _encode_multipart(fields={}, files={"bundle": (filename, bundle_bytes, "application/zip")})
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        INSTALL_ID_HEADER: str(INSTALL_ID or ""),
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status, resp.read()
    except HTTPError as e:
        try:
            return int(getattr(e, "code", 0) or 0), e.read() or b""
        except Exception:
            return int(getattr(e, "code", 0) or 0), b""


def _support_payload_base() -> dict:
    return {
        "install_id": INSTALL_ID,
        "app_id": APP_ID,
        "app_version": APP_VERSION,
        "channel": APP_CHANNEL or None,
        "arch": platform.machine(),
        "ts": int(time.time()),
    }


def _support_checkin_once():
    try:
        now = time.time()
        st = _read_json(CHECKIN_STATE_PATH)
        last = float(st.get("last_ping_at") or 0.0)
        if (now - last) < float(24 * 60 * 60):
            return
        payload = {"app": "Curtis BCH", "version": APP_VERSION}
        _post_json(SUPPORT_CHECKIN_URL, payload, timeout_s=6, headers={INSTALL_ID_HEADER: str(INSTALL_ID or "")})
        _write_json(CHECKIN_STATE_PATH, {"last_ping_at": now})
    except Exception:
        pass


def _support_checkin_loop(stop_event: threading.Event):
    _support_checkin_once()
    while not stop_event.is_set():
        stop_event.wait(24 * 60 * 60)
        if stop_event.is_set():
            break
        _support_checkin_once()

def _read_conf_kv(path: Path):
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


_CONF_LINE_RE = re.compile(r"^\s*(#\s*)?(?P<key>[A-Za-z0-9_]+)\s*=\s*(?P<value>.*)\s*$")


def _set_conf_key(lines: list[str], key: str, value: str | None, *, comment_out: bool = False):
    found = False
    for i, line in enumerate(lines):
        m = _CONF_LINE_RE.match(line)
        if not m:
            continue
        if m.group("key") != key:
            continue
        found = True
        if value is None:
            lines[i] = f"# {key}=1"
        else:
            lines[i] = f"{key}={value}" if not comment_out else f"# {key}={value}"
    if not found and value is not None:
        lines.append(f"{key}={value}")


def _update_node_conf(network: str, prune: int, txindex: int):
    NODE_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)
    if NODE_CONF_PATH.exists():
        lines = NODE_CONF_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        lines = []

    network = network.lower().strip()
    if network not in ["mainnet", "testnet", "regtest"]:
        raise ValueError("invalid network")

    _set_conf_key(lines, "txindex", str(int(bool(txindex))))
    _set_conf_key(lines, "prune", str(int(prune)))

    if network == "mainnet":
        _set_conf_key(lines, "testnet", "1", comment_out=True)
        _set_conf_key(lines, "regtest", "1", comment_out=True)
    elif network == "testnet":
        _set_conf_key(lines, "testnet", "1", comment_out=False)
        _set_conf_key(lines, "regtest", "1", comment_out=True)
    else:
        _set_conf_key(lines, "testnet", "1", comment_out=True)
        _set_conf_key(lines, "regtest", "1", comment_out=False)

    NODE_CONF_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _tail_text(path: Path, *, max_bytes: int = 64 * 1024) -> str:
    try:
        if not path.exists():
            return ""
        size = path.stat().st_size
        start = max(0, size - max_bytes)
        with path.open("rb") as f:
            f.seek(start)
            raw = f.read()
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _detect_reindex_required() -> bool:
    txt = _tail_text(NODE_LOG_PATH)
    if not txt:
        return False
    lowered = txt.lower()
    return ("previously been pruned" in lowered) and ("reindex" in lowered)


def _request_reindex_chainstate():
    try:
        NODE_REINDEX_FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
        NODE_REINDEX_FLAG_PATH.write_text(str(int(time.time())) + "\n", encoding="utf-8")
    except Exception:
        pass


def _build_support_bundle_zip(payload: dict) -> tuple[bytes, str]:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ticket.json", json.dumps(payload, indent=2, sort_keys=True))
        zf.writestr("about.json", json.dumps(_about(), indent=2, sort_keys=True))
        zf.writestr("settings.json", json.dumps(_current_settings(), indent=2, sort_keys=True))
    name = f"curtis-bch-support-{int(time.time())}.zip"
    return bio.getvalue(), name


def _current_settings():
    conf = _read_conf_kv(NODE_CONF_PATH)
    try:
        prune = int(conf.get("prune") or 5500)
    except Exception:
        prune = 5500
    network = "testnet4" if str(conf.get("testnet4") or "0").strip().lower() in ("1", "true") else "mainnet"
    return {"prune": prune, "network": network}


def _update_network_conf(network: str):
    network = str(network or "mainnet").strip().lower()
    if network not in ("mainnet", "testnet4"):
        raise ValueError("network must be mainnet or testnet4")
    NODE_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = NODE_CONF_PATH.read_text(encoding="utf-8", errors="replace").splitlines() if NODE_CONF_PATH.exists() else []
    _set_conf_key(lines, "testnet", "0")
    _set_conf_key(lines, "regtest", "0")
    _set_conf_key(lines, "scalenet", "0")
    _set_conf_key(lines, "chipnet", "0")
    _set_conf_key(lines, "testnet4", "1" if network == "testnet4" else "0")
    NODE_CONF_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _update_prune_conf(prune: int):
    NODE_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = NODE_CONF_PATH.read_text(encoding="utf-8", errors="replace").splitlines() if NODE_CONF_PATH.exists() else []
    _set_conf_key(lines, "prune", str(int(prune)))
    NODE_CONF_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

def _node_status():
    info = _rpc_call("getblockchaininfo")
    net = _rpc_call("getnetworkinfo")
    mempool = _rpc_call("getmempoolinfo")

    blocks = int(info.get("blocks") or 0)
    headers = int(info.get("headers") or blocks)
    progress = float(info.get("verificationprogress") or 0.0)
    ibd = bool(info.get("initialblockdownload", False))
    try:
        difficulty = float(info.get("difficulty") or 0.0)
    except Exception:
        difficulty = 0.0

    template_ready = None
    template_error_code = None
    template_error = None
    if not ibd:
        try:
            tmpl = _rpc_call("getblocktemplate", [{}])
            template_ready = isinstance(tmpl, dict) and bool(tmpl)
        except RuntimeError as e:
            template_error_code, template_error = _rpc_error_details(e)
            template_ready = False
        except Exception as e:
            _, template_error = _rpc_error_details(e)
            template_ready = False

    best_block_time = None
    try:
        bh = str(info.get("bestblockhash") or "").strip()
        if bh:
            hdr = _rpc_call("getblockheader", [bh, True]) or {}
            if isinstance(hdr, dict) and hdr.get("time") is not None:
                best_block_time = int(hdr.get("time"))
    except Exception:
        best_block_time = None

    status = {
        "chain": info.get("chain"),
        "blocks": blocks,
        "headers": headers,
        "difficulty": difficulty,
        "verificationprogress": progress,
        "initialblockdownload": ibd,
        "connections": int(net.get("connections") or 0),
        "subversion": str(net.get("subversion") or ""),
        "mempool_bytes": int(mempool.get("bytes") or 0),
        "size_on_disk": int(info.get("size_on_disk") or 0),
        "pruned": bool(info.get("pruned", False)),
        "best_block_time": best_block_time,
        "median_time": int(info.get("mediantime") or 0),
        "warnings": str(info.get("warnings") or net.get("warnings") or "").strip() or None,
        "template_ready": template_ready,
        "template_error_code": template_error_code,
        "template_error": template_error,
    }

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        NODE_CACHE_PATH.write_text(json.dumps({"t": int(time.time()), "status": status}) + "\n", encoding="utf-8")
    except Exception:
        pass

    return status


def _read_node_cache():
    try:
        if not NODE_CACHE_PATH.exists():
            return None
        obj = json.loads(NODE_CACHE_PATH.read_text(encoding="utf-8", errors="replace"))
        t = int(obj.get("t") or 0)
        status = obj.get("status") or {}
        if not isinstance(status, dict):
            return None
        return {"t": t, "status": status}
    except Exception:
        return None


def _about():
    node = None
    node_error = None
    try:
        node = _node_status()
    except Exception as e:
        node_error = str(e)

    return {
        "channel": APP_CHANNEL or None,
        "networkIp": NETWORK_IP or None,
        "images": {
            "bchn": BCHN_IMAGE or None,
            "ckpool": CKPOOL_IMAGE or None,
        },
        "node": node,
        "nodeError": node_error,
        "pool": _pool_settings(),
    }


def _extract_json_obj(text: str):
    s = text.strip()
    if not s:
        raise ValueError("empty json")

    try:
        return json.loads(s)
    except Exception:
        pass

    last = s.rfind("}")
    while last != -1:
        try:
            return json.loads(s[: last + 1])
        except Exception:
            last = s.rfind("}", 0, last)
    raise ValueError("invalid json")


def _to_hashrate_ths(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except Exception:
            return None

    s = str(value).strip()
    if not s:
        return None
    s = s.replace(",", "")
    # Extract leading float (supports scientific notation).
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)", s)
    if not m:
        return None
    try:
        n = float(m.group(1))
    except Exception:
        return None

    rest = s[m.end() :].strip().replace("/", " ")
    # Find unit token like H/KH/MH/GH/TH/PH/EH, but also handle ckpool's
    # shorthand like "78.6G" / "8.06T" (no "H").
    unit = ""
    unit_match = re.search(r"(?i)\b([kmgtep]?h)\b", rest)
    if unit_match:
        unit = unit_match.group(1).lower().strip()
    else:
        shorthand = re.search(r"(?i)\b([kmgtep])\b", rest)
        if shorthand:
            unit = f"{shorthand.group(1).lower()}h"
        elif re.search(r"(?i)\bh\b", rest):
            unit = "h"

    # No unit: assume TH/s (historical behavior of this app).
    if not unit:
        return n

    scale_to_ths = {
        "h": 1e-12,
        "kh": 1e-9,
        "mh": 1e-6,
        "gh": 1e-3,
        "th": 1.0,
        "ph": 1e3,
        "eh": 1e6,
    }
    factor = scale_to_ths.get(unit)
    if factor is None:
        return None
    return n * factor


def _to_lastshare_s(value):
    try:
        if value is None:
            return None
        return int(float(value))
    except Exception:
        return None


def _active_worker_summary(user: dict | None, *, now_s: int | None = None) -> dict:
    now = int(now_s if now_s is not None else time.time())
    rows = user.get("worker") if isinstance(user, dict) and isinstance(user.get("worker"), list) else []

    active_count = 0
    seen_count = 0
    latest_lastshare = None
    summed_windows = {"1m": 0.0, "5m": 0.0, "15m": 0.0, "1h": 0.0, "6h": 0.0, "1d": 0.0, "7d": 0.0}
    observed_windows: set[str] = set()

    for row in rows:
        if not isinstance(row, dict):
            continue
        lastshare_s = _to_lastshare_s(row.get("lastshare"))
        if lastshare_s:
            if latest_lastshare is None or lastshare_s > latest_lastshare:
                latest_lastshare = lastshare_s
            age_s = max(0, now - lastshare_s)
        else:
            age_s = None

        if age_s is not None and age_s <= STALE_WORKER_WINDOW_S:
            seen_count += 1
        if age_s is None or age_s > ACTIVE_WORKER_WINDOW_S:
            continue

        active_count += 1
        window_values = {
            "1m": _to_hashrate_ths(row.get("hashrate1m")),
            "5m": _to_hashrate_ths(row.get("hashrate5m")),
            "15m": _to_hashrate_ths(row.get("hashrate15m")),
            "1h": _to_hashrate_ths(row.get("hashrate1hr") or row.get("hashrate1h")),
            "6h": _to_hashrate_ths(row.get("hashrate6hr") or row.get("hashrate6h")),
            "1d": _to_hashrate_ths(row.get("hashrate1d")),
            "7d": _to_hashrate_ths(row.get("hashrate7d")),
        }
        for key, value in window_values.items():
            if value is None or not math.isfinite(value):
                continue
            observed_windows.add(key)
            summed_windows[key] += float(value)

    if active_count <= 0:
        return {
            "active_workers": 0,
            "seen_workers": seen_count,
            "lastshare": latest_lastshare,
            "hashrate_ths": 0.0,
            "hashrates_ths": dict(summed_windows),
        }

    return {
        "active_workers": int(active_count),
        "seen_workers": int(seen_count),
        "lastshare": latest_lastshare,
        "hashrate_ths": float(summed_windows["1m"]),
        "hashrates_ths": {key: float(summed_windows[key]) for key in observed_windows},
    }


def _read_ckpool_conf():
    if not CKPOOL_CONF_PATH.exists():
        return {}
    return _extract_json_obj(CKPOOL_CONF_PATH.read_text(encoding="utf-8", errors="replace"))


def _write_ckpool_conf(conf: dict):
    CKPOOL_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)
    CKPOOL_CONF_PATH.write_text(json.dumps(conf, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _heal_ckpool_conf(conf: dict) -> dict:
    """Normalize legacy Curtis/Axe-era CKPool settings to the current stack."""
    conf = dict(conf or {})
    btcd = conf.get("btcd")
    if not isinstance(btcd, list) or not btcd or not isinstance(btcd[0], dict):
        btcd = [{}]
        conf["btcd"] = btcd
    btcd[0]["url"] = "bchn:28332"
    btcd[0]["auth"] = BCH_RPC_USER
    btcd[0]["pass"] = BCH_RPC_PASS
    btcd[0]["notify"] = True

    conf["webdir"] = "/www/pool"
    conf["userdir"] = "/www/users"
    conf.setdefault("logdir", "/www")
    conf.setdefault("serverurl", ["0.0.0.0:3333"])
    conf.setdefault("mindiff", 1)
    conf.setdefault("startdiff", 16)
    conf.setdefault("maxdiff", 0)
    conf.setdefault("btcsig", "/Curtis BCH/")
    conf["zmqblock"] = "tcp://bchn:28334"
    return conf


def _pool_settings():
    conf_addr = ""
    validation_warning = None
    validated = None
    mindiff = None
    startdiff = None
    maxdiff = None
    try:
        raw_conf = _read_ckpool_conf()
        conf = _heal_ckpool_conf(raw_conf)
        if conf != raw_conf:
            _write_ckpool_conf(conf)
        conf_addr = str(conf.get("btcaddress") or "").strip()
        validation_warning = conf.get("validationWarning")
        validated = conf.get("validated")
        mindiff = conf.get("mindiff")
        startdiff = conf.get("startdiff")
        maxdiff = conf.get("maxdiff")
    except Exception:
        conf_addr = ""

    payout_address = conf_addr
    configured = bool(payout_address) and payout_address not in [
        CKPOOL_FALLBACK_DONATION_ADDRESS,
        "CHANGEME_BCH_PAYOUT_ADDRESS",
    ]

    if not isinstance(validation_warning, str):
        validation_warning = None
    if validated is not None:
        validated = bool(validated)

    def _to_int(v, default: int) -> int:
        try:
            if isinstance(v, bool):
                return int(default)
            if isinstance(v, int):
                return int(v)
            if isinstance(v, float):
                if not math.isfinite(v):
                    return int(default)
                if float(int(v)) != float(v):
                    return int(default)
                return int(v)
            s = str(v).strip()
            if not re.fullmatch(r"[0-9]+", s):
                return int(default)
            return int(s)
        except Exception:
            return int(default)

    return {
        "payoutAddress": payout_address or "",
        "configured": configured,
        "validated": validated,
        "validationWarning": validation_warning,
        "mindiff": _to_int(mindiff, 1),
        "startdiff": _to_int(startdiff, 16),
        "maxdiff": _to_int(maxdiff, 0),
        "warning": (
            "Set a payout address before mining. If unset, ckpool may default to a donation address."
            if not configured
            else None
        ),
    }


_CASHADDR_RE = re.compile(r"^(?:(?:bitcoincash|bchtest|bchreg):)?(?P<body>[qp][0-9a-z]{41,60})$", re.IGNORECASE)
_LEGACY_RE = re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$")

_CASHADDR_HELP_URL = "https://bch.info/en/tools/cashaddr"
_CASHADDR_ALPHABET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_CASHADDR_ALPHABET_REV = {c: i for i, c in enumerate(_CASHADDR_ALPHABET)}
_CASHADDR_POLYMOD_GEN = (
    0x98F2BC8E61,
    0x79B76D99E2,
    0xF33E5FB3C4,
    0xAE2EABE2A8,
    0x1E4F43E470,
)
_CASHADDR_SIZE_MAP = {0: 20, 1: 24, 2: 28, 3: 32, 4: 40, 5: 48, 6: 56, 7: 64}


def _cashaddr_prefix_expand(prefix: str) -> list[int]:
    return [ord(ch) & 0x1F for ch in prefix] + [0]


def _cashaddr_polymod(values: list[int]) -> int:
    chk = 1
    for v in values:
        top = chk >> 35
        chk = ((chk & 0x07FFFFFFFF) << 5) ^ v
        for i in range(5):
            if (top >> i) & 1:
                chk ^= _CASHADDR_POLYMOD_GEN[i]
    return chk


def _cashaddr_verify_checksum(prefix: str, payload: list[int]) -> bool:
    # CashAddr checksum constant is 1 (i.e. polymod == 1)
    return _cashaddr_polymod(_cashaddr_prefix_expand(prefix) + payload) == 1


def _convertbits(data: list[int], frombits: int, tobits: int, pad: bool) -> list[int]:
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            raise ValueError("invalid value")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    else:
        if bits >= frombits:
            raise ValueError("illegal zero padding")
        if (acc << (tobits - bits)) & maxv:
            raise ValueError("non-zero padding")
    return ret


def _base58check_encode(prefix_byte: int, payload: bytes) -> str:
    raw = bytes([prefix_byte]) + payload
    chk = hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    b = raw + chk

    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(b, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = alphabet[r] + out

    leading_zeros = 0
    for c in b:
        if c == 0:
            leading_zeros += 1
        else:
            break
    return ("1" * leading_zeros) + out


def _cashaddr_to_legacy(addr: str) -> tuple[str, bool]:
    a = (addr or "").strip()
    if _LEGACY_RE.match(a):
        return a, False

    m = _CASHADDR_RE.match(a)
    if not m:
        raise ValueError("payoutAddress must be a CashAddr (q/p...) or legacy (1/3...) BCH address")

    prefix = "bitcoincash"
    if ":" in a:
        prefix = a.split(":", 1)[0].lower()
    body = m.group("body").lower()
    data = [_CASHADDR_ALPHABET_REV[ch] for ch in body]
    if not _cashaddr_verify_checksum(prefix, data):
        raise ValueError("payoutAddress has an invalid CashAddr checksum")

    payload_no_checksum = data[:-8]
    decoded = _convertbits(payload_no_checksum, 5, 8, pad=False)
    version = decoded[0]
    h = bytes(decoded[1:])

    addr_type = version >> 3
    size_code = version & 7
    expected_len = _CASHADDR_SIZE_MAP.get(size_code)
    if expected_len is None or len(h) != expected_len:
        raise ValueError("payoutAddress has an unexpected hash size")

    if addr_type == 0:
        return _base58check_encode(0x00, h), True  # P2PKH
    if addr_type == 1:
        return _base58check_encode(0x05, h), True  # P2SH

    raise ValueError("payoutAddress must be a P2PKH or P2SH address")


def _looks_like_bch_address(addr: str) -> bool:
    a = (addr or "").strip()
    return bool(_CASHADDR_RE.match(a) or _LEGACY_RE.match(a))


def _update_pool_settings(*, payout_address: str):
    return _update_pool_settings_full(payout_address=payout_address)


def _update_pool_settings_full(
    *,
    payout_address: str,
    mindiff=None,
    startdiff=None,
    maxdiff=None,
):
    addr_raw = payout_address.strip()
    if not addr_raw:
        raise ValueError("payoutAddress is required")

    addr_legacy, converted_from_cashaddr = _cashaddr_to_legacy(addr_raw)

    validated = None
    validation_warning = None
    conversion_notice = None
    if converted_from_cashaddr:
        conversion_notice = (
            f"CashAddr detected; converted locally on your 5tratumOS to legacy format for ckpool compatibility: {addr_legacy}. "
            f"Reference converter: {_CASHADDR_HELP_URL}"
        )
    try:
        res = _rpc_call("validateaddress", [addr_legacy]) or {}
        validated = bool(res.get("isvalid"))
        if not validated:
            raise ValueError("payoutAddress is not a valid BCH address")
    except Exception:
        validated = False
        validation_warning = (
            "Node RPC unavailable; saved without RPC validation. Double-check your address, then restart the app."
        )
        if conversion_notice:
            validation_warning = f"{validation_warning} {conversion_notice}"

    conf = _heal_ckpool_conf(_read_ckpool_conf())
    # ckpool expects a legacy/Base58 address here.
    conf["btcaddress"] = addr_legacy
    # Ensure ckpool writes pool stats files for the UI (older configs may miss these).
    conf["webdir"] = "/www/pool"
    conf["userdir"] = "/www/users"
    _record_payout_history(addr_legacy)

    def _maybe_int(v):
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return int(v)
        if isinstance(v, float):
            if not math.isfinite(v):
                return None
            if float(int(v)) != float(v):
                raise ValueError("difficulty values must be whole numbers (ckpool does not support fractional difficulties)")
            return int(v)
        s = str(v).strip()
        if s == "":
            return None
        if not re.fullmatch(r"[0-9]+", s):
            raise ValueError("difficulty values must be whole numbers (ckpool does not support fractional difficulties)")
        return int(s)

    md = _maybe_int(mindiff)
    sd = _maybe_int(startdiff)
    xd = _maybe_int(maxdiff)

    # If any diff value is provided, validate and apply; otherwise keep existing config.
    if md is not None or sd is not None or xd is not None:
        md = md if md is not None else int(conf.get("mindiff") or 1)
        sd = sd if sd is not None else int(conf.get("startdiff") or 16)
        xd = xd if xd is not None else int(conf.get("maxdiff") or 0)

        if md < 1:
            raise ValueError("mindiff must be >= 1")
        if sd < 1:
            raise ValueError("startdiff must be >= 1")
        if sd < md:
            raise ValueError("startdiff must be >= mindiff")
        if xd < 0:
            raise ValueError("maxdiff must be 0 (no limit) or >= startdiff")
        if xd != 0 and xd < sd:
            raise ValueError("maxdiff must be 0 (no limit) or >= startdiff")

        conf["mindiff"] = md
        conf["startdiff"] = sd
        conf["maxdiff"] = xd
    else:
        # Self-heal older configs that don't include these keys (keep existing defaults).
        conf.setdefault("mindiff", 1)
        conf.setdefault("startdiff", 16)
        conf.setdefault("maxdiff", 0)

    conf["validated"] = bool(validated) if validated is not None else False
    if conversion_notice and not validation_warning:
        validation_warning = conversion_notice

    if validation_warning:
        conf["validationWarning"] = validation_warning
    else:
        conf.pop("validationWarning", None)
    _write_ckpool_conf(conf)
    try:
        with CKPOOL_CONF_PATH.open("rb") as fh:
            os.fsync(fh.fileno())
    except Exception:
        pass

    return _pool_settings()


def _read_ckpool_status_file(filename: str) -> str:
    bases = [
        CKPOOL_STATUS_DIR,
        Path("/data/pool/www/pool"),
        Path("/data/pool/www"),
    ]
    seen = set()
    empty: list[tuple[float, str]] = []

    def read_candidate(path: Path) -> tuple[float, str] | None:
        try:
            if not (path.exists() and path.is_file()):
                return None
            return (float(path.stat().st_mtime), path.read_text(encoding="utf-8", errors="replace").strip())
        except Exception:
            return None

    # Check the known ckpool locations first and return immediately. The fallback
    # glob can be expensive on long-running installs with many pool files.
    for base in bases:
        if not isinstance(base, Path):
            continue
        for path in [
            base / filename,
            base.parent / filename,
            base / "pool" / filename,
            base.parent / "pool" / filename,
        ]:
            if path in seen:
                continue
            seen.add(path)
            item = read_candidate(path)
            if item is None:
                continue
            if item[1]:
                return item[1]
            empty.append(item)

    entries: list[tuple[float, str]] = []
    for base in bases:
        if not isinstance(base, Path):
            continue
        try:
            for path in base.glob(f"*/{filename}"):
                if path in seen:
                    continue
                seen.add(path)
                item = read_candidate(path)
                if item is not None:
                    entries.append(item)
        except Exception:
            continue

    non_empty = [e for e in entries if e[1]]
    if non_empty:
        return max(non_empty, key=lambda x: x[0])[1]
    if entries:
        return max(entries, key=lambda x: x[0])[1]
    if empty:
        return max(empty, key=lambda x: x[0])[1]
    return ""


def _read_pool_status_raw():
    return _read_ckpool_status_file("pool.status")

def _read_pool_workers_raw():
    return _read_ckpool_status_file("pool.workers")


def _parse_pool_status(raw: str):
    if not raw:
        return {"workers": 0, "hashrate_ths": None, "best_share": None}

    def to_int(value):
        try:
            return int(str(value).strip())
        except Exception:
            return 0

    def to_hashrate_ths(value):
        return _to_hashrate_ths(value)

    def normalize(data: dict):
        if not isinstance(data, dict):
            return {"workers": 0, "hashrate_ths": None, "best_share": None}
        workers = (
            data.get("workers")
            or data.get("Workers")
            or data.get("Users")
            or data.get("users")
            or data.get("active_workers")
            or data.get("activeWorkers")
        )

        hashrates_raw = {
            "1m": data.get("hashrate1m"),
            "5m": data.get("hashrate5m"),
            "15m": data.get("hashrate15m"),
            "1h": data.get("hashrate1hr") or data.get("hashrate1h"),
            "6h": data.get("hashrate6hr") or data.get("hashrate6h"),
            "1d": data.get("hashrate1d"),
            "7d": data.get("hashrate7d"),
        }
        hashrates_ths = {}
        for k, v in hashrates_raw.items():
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            hashrates_ths[k] = to_hashrate_ths(v)

        hashrate = (
            data.get("hashrate_ths")
            or data.get("hashrateThs")
            or data.get("hashrate")
            or data.get("Hashrate")
            or data.get("rate")
        )
        if hashrate is None:
            for k in ["1m", "5m", "15m", "1h", "6h", "1d", "7d"]:
                if k in hashrates_raw and hashrates_raw[k] is not None:
                    hashrate = hashrates_raw[k]
                    break

        best_share = data.get("bestshare") or data.get("best_share") or data.get("bestShare") or data.get("best")
        accepted = data.get("accepted")
        rejected = data.get("rejected")
        runtime = data.get("runtime")
        lastupdate = data.get("lastupdate") or data.get("last_update") or data.get("LastUpdate")

        # Backward-compatible "hashrate_ths" should reflect the 1-minute window when available.
        hashrate_ths = to_hashrate_ths(hashrate)
        try:
            hr1m = hashrates_ths.get("1m")
            if hr1m is not None and math.isfinite(float(hr1m)):
                hashrate_ths = float(hr1m)
        except Exception:
            pass
        return {
            "workers": to_int(workers),
            "hashrate_ths": hashrate_ths,
            "best_share": best_share,
            "hashrates_ths": hashrates_ths or None,
            "accepted": to_int(accepted) if accepted is not None else None,
            "rejected": to_int(rejected) if rejected is not None else None,
            "runtime": to_int(runtime) if runtime is not None else None,
            "lastupdate": to_int(lastupdate) if lastupdate is not None else None,
        }

    def merge_json_objects(text: str) -> dict | None:
        merged = {}
        found = False
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if not (line.startswith("{") and line.endswith("}")):
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                merged.update(obj)
                found = True
        return merged if found else None

    merged = merge_json_objects(raw)
    if merged is not None:
        return normalize(merged)

    # Prefer JSON (ckpool often writes JSON, but can include extra log noise).
    try:
        return normalize(_extract_json_obj(raw))
    except Exception:
        try:
            start = raw.find("{")
            if start != -1:
                return normalize(_extract_json_obj(raw[start:]))
        except Exception:
            pass

    # Fallback: parse key/value lines.
    data = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
        elif ":" in line:
            key, val = line.split(":", 1)
        else:
            continue
        data[key.strip()] = val.strip()

    return normalize(data)

def _parse_pool_workers(raw: str):
    if not raw:
        return []

    # Best case: JSON list or object
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Some formats store under a key
            for key in ["workers", "data", "result"]:
                if isinstance(data.get(key), list):
                    return data[key]
            # Or a dict keyed by worker
            if all(isinstance(v, dict) for v in data.values()):
                out = []
                for k, v in data.items():
                    item = dict(v)
                    item.setdefault("worker", k)
                    out.append(item)
                return out
    except Exception:
        pass

    # Fallback: parse lines "worker ... lastshare ..."
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p for p in line.replace("\t", " ").split(" ") if p]
        if not parts:
            continue
        out.append({"worker": parts[0], "raw": line})
    return out


def _support_ticket_payload(*, subject: str, message: str, email: str | None):
    diagnostics = {}
    try:
        node = _node_status()
        diagnostics["node"] = {
            "chain": node.get("chain"),
            "blocks": node.get("blocks"),
            "headers": node.get("headers"),
            "progress": node.get("verificationprogress"),
            "connections": node.get("connections"),
            "subversion": node.get("subversion"),
            "mempool_bytes": node.get("mempool_bytes"),
        }
    except Exception as e:
        diagnostics["node_error"] = str(e)

    try:
        pool = _parse_pool_status(_read_pool_status_raw())
        diagnostics["pool"] = {
            "workers": pool.get("workers"),
            "hashrate_ths": pool.get("hashrate_ths"),
            "best_share": pool.get("best_share"),
        }
    except Exception as e:
        diagnostics["pool_error"] = str(e)

    payload = _support_payload_base()
    payload.update(
        {
            "type": "support_ticket",
            "subject": subject,
            "message": message,
            "email": email or None,
            "diagnostics": diagnostics,
        }
    )
    return payload


def _now_ms():
    return int(time.time() * 1000)


class PoolSeries:
    def __init__(self):
        self._lock = threading.Lock()
        self._points: list[dict] = []

    def load(self):
        cutoff_ms = _now_ms() - (MAX_RETENTION_S * 1000)
        points: list[dict] = []
        if POOL_SERIES_PATH.exists():
            for line in POOL_SERIES_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    t = int(obj.get("t") or 0)
                    if t >= cutoff_ms:
                        points.append(obj)
                except Exception:
                    continue

        points.sort(key=lambda p: p.get("t", 0))
        if len(points) > MAX_SERIES_POINTS:
            points = points[-MAX_SERIES_POINTS:]

        with self._lock:
            self._points = points

        # Rewrite the file if we dropped old points or it's missing.
        self._rewrite(points)

    def _rewrite(self, points: list[dict]):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = POOL_SERIES_PATH.with_suffix(".tmp")
        tmp.write_text("\n".join(json.dumps(p, separators=(",", ":")) for p in points) + ("\n" if points else ""), encoding="utf-8")
        tmp.replace(POOL_SERIES_PATH)

    def append(self, point: dict):
        cutoff_ms = _now_ms() - (MAX_RETENTION_S * 1000)
        with self._lock:
            self._points.append(point)
            self._points = [p for p in self._points if int(p.get("t") or 0) >= cutoff_ms]
            if len(self._points) > MAX_SERIES_POINTS:
                self._points = self._points[-MAX_SERIES_POINTS:]

            STATE_DIR.mkdir(parents=True, exist_ok=True)
            with POOL_SERIES_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(point, separators=(",", ":")) + "\n")

            # Occasionally compact the file (simple heuristic).
            if POOL_SERIES_PATH.stat().st_size > 10 * 1024 * 1024:
                self._rewrite(self._points)

    def query(self, trail: str, max_points: int = 1000):
        trail = (trail or "").strip().lower()
        seconds = {
            "30m": 30 * 60,
            "6h": 6 * 60 * 60,
            "12h": 12 * 60 * 60,
            "1d": 24 * 60 * 60,
            "3d": 3 * 24 * 60 * 60,
            "6d": 6 * 24 * 60 * 60,
            "7d": 7 * 24 * 60 * 60,
        }.get(trail, 30 * 60)

        cutoff_ms = _now_ms() - (seconds * 1000)
        with self._lock:
            pts = [p for p in self._points if int(p.get("t") or 0) >= cutoff_ms]

        if len(pts) <= max_points:
            return pts

        stride = (len(pts) + max_points - 1) // max_points
        return pts[::stride]


POOL_SERIES = PoolSeries()


def _series_sampler(stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            status = _parse_pool_status(_read_pool_status_raw())
            user = _read_ckpool_user_stats()
            active_summary = _active_worker_summary(user)
            workers = active_summary.get("active_workers") if isinstance(active_summary, dict) else status.get("workers")
            try:
                workers_i = int(workers)
            except Exception:
                workers_i = 0

            def to_float(value):
                if value is None:
                    return None
                try:
                    return float(value)
                except Exception:
                    return None

            hashrates = status.get("hashrates_ths") or {}
            if not isinstance(hashrates, dict):
                hashrates = {}
            if isinstance(active_summary, dict):
                active_hashrates = active_summary.get("hashrates_ths")
                if isinstance(active_hashrates, dict):
                    merged = dict(hashrates)
                    merged.update(active_hashrates)
                    hashrates = merged

            hashrate_f = to_float(
                active_summary.get("hashrate_ths") if isinstance(active_summary, dict) else hashrates.get("1m", status.get("hashrate_ths"))
            )

            try:
                node = _node_status()
                net_diff = to_float(node.get("difficulty"))
                net_height = int(node.get("blocks") or 0)
            except Exception:
                net_diff = None
                net_height = None

            _scan_ckpool_log_for_block_events()
            _sync_trackers_to_latest_block_event()
            _update_round_effort_tracker(
                pool_status=status,
                network_difficulty=net_diff,
                events=_snapshot_block_events(),
            )

            POOL_SERIES.append(
                {
                    "t": _now_ms(),
                    "workers": workers_i,
                    # Backward-compatible single-series hashrate (1m best-effort).
                    "hashrate_ths": hashrate_f,
                    # ckpool windowed hashrates for multi-line charts.
                    "hashrate_1m_ths": to_float(hashrates.get("1m")),
                    "hashrate_5m_ths": to_float(hashrates.get("5m")),
                    "hashrate_15m_ths": to_float(hashrates.get("15m")),
                    "hashrate_1h_ths": to_float(hashrates.get("1h")),
                    "hashrate_6h_ths": to_float(hashrates.get("6h")),
                    "hashrate_1d_ths": to_float(hashrates.get("1d")),
                    "hashrate_7d_ths": to_float(hashrates.get("7d")),
                    "network_difficulty": net_diff,
                    "network_height": net_height,
                }
            )

            _scan_ckpool_sharelogs_for_trackers(network_height=net_height)
        except Exception:
            pass

        stop_event.wait(SAMPLE_INTERVAL_S)


def _backscan_worker(stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            _maybe_backscan_blocks(max_blocks=BACKSCAN_DEFAULT_MAX_BLOCKS)
            _sync_trackers_to_latest_block_event()
        except Exception:
            pass
        stop_event.wait(5)


def _widget_sync():
    try:
        s = _node_status()
        progress = max(0.0, min(1.0, float(s["verificationprogress"])))
        syncing = bool(s["initialblockdownload"])
        if not syncing:
            progress = 1.0
        pct = int(progress * 100)
        label = "In progress" if syncing else "Synchronized"
        return {
            "type": "text-with-progress",
            "title": "BCH sync",
            "text": f"{pct}%",
            "progressLabel": label,
            "progress": progress,
        }
    except Exception:
        return {
            "type": "text-with-progress",
            "title": "BCH sync",
            "text": "-",
            "progressLabel": "Unavailable",
            "progress": 0,
        }


def _widget_pool():
    p = _pool_api_cached()
    return {
        "type": "three-stats",
        "items": [
            {"title": "Hashrate", "text": str(p.get("hashrate_ths") if p.get("hashrate_ths") is not None else "-"), "subtext": "TH/s"},
            {"title": "Workers", "text": str(p.get("workers") or 0)},
            {"title": "Best Share", "text": str(p.get("best_share") if p.get("best_share") is not None else "-")},
        ],
    }


def _read_json_file(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
        if not raw:
            return {}
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _write_json_file(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _pool_cache_load() -> None:
    try:
        obj = _read_json_file(POOL_CACHE_PATH)
        if not isinstance(obj, dict):
            return
        with _POOL_CACHE_LOCK:
            _POOL_CACHE.clear()
            _POOL_CACHE.update(obj)
    except Exception:
        return


def _pool_workers_cache_load() -> None:
    try:
        obj = _read_json_file(POOL_WORKERS_CACHE_PATH)
        if not isinstance(obj, dict):
            return
        with _POOL_WORKERS_CACHE_LOCK:
            _POOL_WORKERS_CACHE.clear()
            _POOL_WORKERS_CACHE.update(obj)
    except Exception:
        return


def _pool_cache_set(data: dict | None, error: str | None = None) -> None:
    now = time.time()
    entry: dict = {"t": now}
    if isinstance(data, dict):
        entry["pool"] = data
    if error:
        entry["error"] = str(error)
    with _POOL_CACHE_LOCK:
        _POOL_CACHE.clear()
        _POOL_CACHE.update(entry)
    try:
        _write_json_file(POOL_CACHE_PATH, entry)
    except Exception:
        pass


def _pool_workers_cache_set(data: dict | None, error: str | None = None) -> None:
    now = time.time()
    entry: dict = {"t": now}
    if isinstance(data, dict):
        entry["workers"] = data
    if error:
        entry["error"] = str(error)
    with _POOL_WORKERS_CACHE_LOCK:
        _POOL_WORKERS_CACHE.clear()
        _POOL_WORKERS_CACHE.update(entry)
    try:
        _write_json_file(POOL_WORKERS_CACHE_PATH, entry)
    except Exception:
        pass


def _patch_bestshare_caches(
    *,
    reset_at: int | None = None,
    reset_worker: str | None = None,
    best_share_since_block: int | None = None,
    best_share_since_block_worker: str | None = None,
) -> None:
    """Make reset results visible immediately instead of serving stale cache data."""
    now = time.time()
    worker = str(reset_worker or "").strip()
    worker_suffix = worker.split(".")[-1].strip() if "." in worker else worker

    pool_snapshot = None
    with _POOL_CACHE_LOCK:
        pool = _POOL_CACHE.get("pool") if isinstance(_POOL_CACHE.get("pool"), dict) else None
        if pool is not None:
            updated_pool = dict(pool)
            updated_pool["best_share_since_block"] = _best_share_int(best_share_since_block)
            updated_pool["best_share_since_block_worker"] = (
                str(best_share_since_block_worker or "").strip() or None
            )
            if reset_at is not None:
                updated_pool["best_share_reset_at"] = int(reset_at)
            _POOL_CACHE["pool"] = updated_pool
            _POOL_CACHE["t"] = now
            _POOL_CACHE.pop("error", None)
            pool_snapshot = dict(_POOL_CACHE)
    if pool_snapshot is not None:
        try:
            _write_json_file(POOL_CACHE_PATH, pool_snapshot)
        except Exception:
            pass

    workers_snapshot = None
    with _POOL_WORKERS_CACHE_LOCK:
        cached_workers = (
            _POOL_WORKERS_CACHE.get("workers")
            if isinstance(_POOL_WORKERS_CACHE.get("workers"), dict)
            else None
        )
        if cached_workers is not None:
            updated_workers = dict(cached_workers)
            rows = []
            for original in cached_workers.get("workers_details") or []:
                if not isinstance(original, dict):
                    continue
                row = dict(original)
                name = str(row.get("workername") or "").strip()
                name_suffix = name.split(".")[-1].strip() if "." in name else name
                if not worker or name == worker or (worker_suffix and name_suffix == worker_suffix):
                    row["bestshare_since_block"] = None
                rows.append(row)
            updated_workers["workers_details"] = rows
            _POOL_WORKERS_CACHE["workers"] = updated_workers
            _POOL_WORKERS_CACHE["t"] = now
            _POOL_WORKERS_CACHE.pop("error", None)
            workers_snapshot = dict(_POOL_WORKERS_CACHE)
    if workers_snapshot is not None:
        try:
            _write_json_file(POOL_WORKERS_CACHE_PATH, workers_snapshot)
        except Exception:
            pass


def _pool_cache_get(*, max_age_s: float) -> dict | None:
    try:
        max_age = float(max_age_s)
    except Exception:
        max_age = 0.0
    if max_age <= 0:
        return None
    with _POOL_CACHE_LOCK:
        entry = dict(_POOL_CACHE) if isinstance(_POOL_CACHE, dict) else {}
    if not entry:
        return None
    try:
        age = time.time() - float(entry.get("t") or 0.0)
    except Exception:
        age = None
    if age is None or age < 0 or age > max_age:
        return None
    return entry


def _pool_workers_cache_get(*, max_age_s: float) -> dict | None:
    try:
        max_age = float(max_age_s)
    except Exception:
        max_age = 0.0
    if max_age <= 0:
        return None
    with _POOL_WORKERS_CACHE_LOCK:
        entry = dict(_POOL_WORKERS_CACHE) if isinstance(_POOL_WORKERS_CACHE, dict) else {}
    if not entry:
        return None
    try:
        age = time.time() - float(entry.get("t") or 0.0)
    except Exception:
        age = None
    if age is None or age < 0 or age > max_age:
        return None
    return entry


def _pool_api_cached() -> dict:
    cached = _pool_cache_get(max_age_s=POOL_CACHE_TTL_S)
    if cached and isinstance(cached.get("pool"), dict):
        out = dict(cached["pool"])
        out["cached"] = True
        try:
            out["cache_age_s"] = max(0.0, time.time() - float(cached.get("t") or 0.0))
        except Exception:
            pass
        if cached.get("error"):
            out["stale_error"] = str(cached.get("error") or "")
        return out
    return {
        "cached": True,
        "error": "warming up",
        "workers": 0,
        "hashrate_ths": None,
        "best_share": None,
        "best_share_all_time": None,
        "best_share_since_block": None,
        "best_share_since_block_worker": None,
        "eta_seconds": None,
        "eta_text": None,
        "network_difficulty": None,
        "network_height": None,
        "network_algo": None,
    }


def _pool_workers_api_cached() -> dict:
    cached = _pool_workers_cache_get(max_age_s=POOL_WORKERS_CACHE_TTL_S)
    if cached and isinstance(cached.get("workers"), dict):
        out = dict(cached["workers"])
        out["cached"] = True
        try:
            out["cache_age_s"] = max(0.0, time.time() - float(cached.get("t") or 0.0))
        except Exception:
            pass
        if cached.get("error"):
            out["stale_error"] = str(cached.get("error") or "")
        return out
    return {"cached": True, "error": "warming up", "workers": 0, "workers_details": []}


def _pool_cache_worker(stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            data = _pool_api()
            _pool_cache_set(data, error=None)
        except Exception as e:
            try:
                with _POOL_CACHE_LOCK:
                    last_pool = dict(_POOL_CACHE.get("pool") or {}) if isinstance(_POOL_CACHE.get("pool"), dict) else None
                _pool_cache_set(last_pool, error=str(e))
            except Exception:
                pass
        stop_event.wait(max(1.0, float(POOL_CACHE_REFRESH_S)))


def _pool_workers_cache_worker(stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            data = _pool_workers_api()
            _pool_workers_cache_set(data, error=None)
        except Exception as e:
            try:
                with _POOL_WORKERS_CACHE_LOCK:
                    last_workers = (
                        dict(_POOL_WORKERS_CACHE.get("workers") or {})
                        if isinstance(_POOL_WORKERS_CACHE.get("workers"), dict)
                        else None
                    )
                _pool_workers_cache_set(last_workers, error=str(e))
            except Exception:
                pass
        stop_event.wait(max(1.0, float(POOL_WORKERS_CACHE_REFRESH_S)))


def _best_share_int(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        try:
            return int(value)
        except Exception:
            return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if re.match(r"^[0-9]+$", s):
            return int(s)
        return int(float(s))
    except Exception:
        return None


def _safe_int(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        if re.match(r"^[+-]?[0-9]+$", s):
            return int(s)
        return int(float(s))
    except Exception:
        return None


def _safe_float(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            f = float(value)
        except Exception:
            return None
        return f if math.isfinite(f) else None
    s = str(value).strip()
    if not s:
        return None
    try:
        f = float(s)
    except Exception:
        return None
    return f if math.isfinite(f) else None


def _iso_utc(value) -> str | None:
    ts = _safe_float(value)
    if ts is None or ts <= 0:
        return None
    if ts > 1_000_000_000_000:
        ts = ts / 1000.0
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


def _format_duration(seconds: float | int | None) -> str | None:
    try:
        if seconds is None:
            return None
        s = float(seconds)
        if not math.isfinite(s) or s < 0:
            return None
        s = int(s)
    except Exception:
        return None

    if s < 60:
        return f"{s}s"
    m, _ = divmod(s, 60)
    if m < 60:
        return f"{m}m"
    h, m = divmod(m, 60)
    if h < 48:
        return f"{h}h {m}m"
    d, h = divmod(h, 24)
    return f"{d}d {h}h"


def _block_event_sort_key(event: dict) -> tuple[int, int]:
    if not isinstance(event, dict):
        return (0, 0)
    t = _safe_int(event.get("t")) or _safe_int(event.get("detected_at")) or 0
    height = _safe_int(event.get("height")) or 0
    return (t, height)


def _normalize_block_event(event: dict | None) -> dict | None:
    if not isinstance(event, dict):
        return None

    block_hash = str(event.get("hash") or "").strip().lower()
    if block_hash and not re.match(r"^[0-9a-f]{64}$", block_hash):
        block_hash = ""

    t = _safe_int(event.get("t")) or _safe_int(event.get("detected_at")) or 0
    height = _safe_int(event.get("height"))
    confirmations = _safe_int(event.get("confirmations"))
    net_diff = _safe_float(event.get("network_difficulty") if event.get("network_difficulty") is not None else event.get("difficulty"))
    solve_diff = _safe_float(event.get("solve_diff"))
    solve_worker = str(event.get("solve_worker") or event.get("miner") or "").strip()
    round_effort = _safe_float(event.get("round_effort") if event.get("round_effort") is not None else event.get("effort"))
    luck_pct = _safe_float(event.get("luck_pct") if event.get("luck_pct") is not None else event.get("luckPct"))
    if luck_pct is None and round_effort is not None:
        luck_pct = round_effort * 100.0
    round_shares = _safe_int(event.get("round_shares") if event.get("round_shares") is not None else event.get("shares"))
    coinbase_txid = str(event.get("coinbase_txid") or "").strip().lower() or None
    source = str(event.get("source") or "app").strip() or "app"
    found_iso = _iso_utc(t)
    status = "confirmed" if confirmations is not None and confirmations > 0 else "found"

    return {
        "t": int(t) if t > 0 else 0,
        "hash": block_hash,
        "height": height,
        "confirmations": confirmations,
        "status": status,
        "network_difficulty": net_diff,
        "solve_diff": solve_diff,
        "solve_worker": solve_worker,
        "miner": solve_worker,
        "round_effort": round_effort,
        "effort": round_effort,
        "luck_pct": luck_pct,
        "luckPct": luck_pct,
        "round_shares": round_shares,
        "shares": round_shares,
        "coinbase_txid": coinbase_txid,
        "source": source,
        "foundAt": found_iso,
        "last_block_found": found_iso,
        "last_block_found_time": found_iso,
        "explorer_block": f"https://blockchair.com/bitcoin-cash/block/{block_hash}" if block_hash else None,
        "explorer_tx": f"https://blockchair.com/bitcoin-cash/transaction/{coinbase_txid}" if coinbase_txid else None,
        "explorer": f"https://blockchair.com/bitcoin-cash/block/{block_hash}" if block_hash else None,
        "log": str(event.get("log") or ""),
    }


def _snapshot_block_events() -> list[dict]:
    state = _read_json_file(BLOCKS_STATE_PATH)
    raw_events = state.get("events") if isinstance(state.get("events"), list) else []
    out: list[dict] = []
    seen: set[str] = set()
    for event in sorted(raw_events, key=_block_event_sort_key, reverse=True):
        normalized = _normalize_block_event(event)
        if not normalized:
            continue
        block_hash = str(normalized.get("hash") or "").strip()
        event_key = block_hash or f"{normalized.get('t') or 0}:{normalized.get('log') or ''}"
        if event_key in seen:
            continue
        seen.add(event_key)
        out.append(normalized)
    return out


def _block_summary_from_events(events: list[dict] | None) -> dict:
    items = events if isinstance(events, list) else _snapshot_block_events()
    blocks_found = len(items)
    summary = {
        "blocksFound": blocks_found,
        "blocks_found": blocks_found,
    }
    if not items:
        return summary

    newest = items[0] if isinstance(items[0], dict) else {}
    found_iso = str(newest.get("foundAt") or newest.get("last_block_found_time") or newest.get("last_block_found") or "").strip() or None
    height = _safe_int(newest.get("height"))
    block_hash = str(newest.get("hash") or "").strip() or None
    source = str(newest.get("source") or "").strip() or None

    if found_iso:
        summary["lastBlockFound"] = found_iso
        summary["last_block_found"] = found_iso
        summary["lastBlockFoundTime"] = found_iso
        summary["last_block_found_time"] = found_iso
        summary["lastPoolBlockTime"] = found_iso
    if height is not None:
        summary["lastBlockFoundHeight"] = height
        summary["last_block_found_height"] = height
        summary["block_height"] = height
        summary["height"] = height
    if block_hash:
        summary["lastBlockFoundHash"] = block_hash
        summary["last_block_hash"] = block_hash
    if source:
        summary["last_block_found_source"] = source
    return summary


def _round_anchor_from_events(events: list[dict] | None) -> tuple[int, str | None]:
    items = events if isinstance(events, list) else _snapshot_block_events()
    newest = items[0] if items and isinstance(items[0], dict) else {}
    anchor_t = _safe_int(newest.get("t")) or 0
    anchor_hash = str(newest.get("hash") or "").strip().lower() or None
    return int(anchor_t), anchor_hash


def _round_effort_anchor(events: list[dict] | None) -> tuple[int, str | None, str]:
    anchor_t, anchor_hash = _round_anchor_from_events(events)
    if anchor_t > 0:
        return anchor_t, anchor_hash, "block"

    pool_state = _read_json_file(POOL_STATE_PATH)
    anchor_t = _safe_int(pool_state.get("round_started_at")) or 0
    return int(anchor_t), None, "tracking-start"


def _round_effort_snapshot(events: list[dict] | None) -> dict:
    state = _read_json_file(ROUND_EFFORT_STATE_PATH)
    if not isinstance(state, dict):
        return {}

    anchor_t, anchor_hash, anchor_source = _round_effort_anchor(events)
    if anchor_t <= 0:
        return {}
    if (_safe_int(state.get("anchor_at")) or 0) != anchor_t:
        return {}
    state_hash = str(state.get("anchor_hash") or "").strip().lower() or None
    if anchor_hash and state_hash != anchor_hash:
        return {}
    state_source = str(state.get("anchor_source") or "").strip()
    if state_source and state_source != anchor_source:
        return {}
    return state


def _update_round_effort_tracker(
    *,
    pool_status: dict,
    network_difficulty: float | None,
    events: list[dict] | None = None,
) -> dict:
    if not _ROUND_EFFORT_UPDATE_LOCK.acquire(blocking=False):
        return _round_effort_snapshot(events)

    try:
        items = events if isinstance(events, list) else _snapshot_block_events()
        anchor_t, anchor_hash, anchor_source = _round_effort_anchor(items)
        if anchor_t <= 0:
            return {}

        anchor_log_time = datetime.fromtimestamp(anchor_t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        state = _read_json_file(ROUND_EFFORT_STATE_PATH)
        if not isinstance(state, dict):
            state = {}

        state_anchor_t = _safe_int(state.get("anchor_at")) or 0
        state_anchor_hash = str(state.get("anchor_hash") or "").strip().lower() or None
        state_anchor_source = str(state.get("anchor_source") or "").strip()
        anchor_changed = (
            state_anchor_t != anchor_t
            or (anchor_hash and state_anchor_hash != anchor_hash)
            or (state_anchor_source and state_anchor_source != anchor_source)
        )
        if anchor_changed:
            state = {
                "version": 1,
                "anchor_at": anchor_t,
                "anchor_hash": anchor_hash,
                "anchor_source": anchor_source,
                "anchor_log_time": anchor_log_time,
                "effort": 0.0,
                "weighted_work": 0,
                "samples": 0,
                "counter_resets": 0,
                "skipped_samples": 0,
                "log_offset": 0,
                "rebuilding": True,
                "coverage_complete": False,
                "updated_at": int(time.time()),
            }
            _write_json_file(ROUND_EFFORT_STATE_PATH, state)

        try:
            log_size = int(CKPOOL_LOG_PATH.stat().st_size)
        except Exception:
            state["rebuilding"] = False
            state["error"] = "ckpool log unavailable"
            state["updated_at"] = int(time.time())
            _write_json_file(ROUND_EFFORT_STATE_PATH, state)
            return state

        offset = _safe_int(state.get("log_offset")) or 0
        full_replay = anchor_changed or offset <= 0
        if offset > log_size:
            # Preserve already-accounted effort if ckpool rotates its log, then
            # establish fresh counter baselines from the replacement file.
            offset = 0
            full_replay = False
            state["last_accepted"] = None
            state["last_runtime"] = None
            state["coverage_complete"] = False
            state["log_reset_at"] = int(time.time())

        effort = _safe_float(state.get("effort")) or 0.0
        weighted_work = _safe_int(state.get("weighted_work")) or 0
        samples = _safe_int(state.get("samples")) or 0
        counter_resets = _safe_int(state.get("counter_resets")) or 0
        skipped_samples = _safe_int(state.get("skipped_samples")) or 0
        previous_accepted = _safe_int(state.get("last_accepted"))
        previous_runtime = _safe_int(state.get("last_runtime"))
        current_runtime = previous_runtime
        current_difficulty = None if full_replay else _safe_float(state.get("last_network_difficulty"))
        if not full_replay and (current_difficulty is None or current_difficulty <= 0):
            current_difficulty = _safe_float(network_difficulty)

        first_log_timestamp = str(state.get("log_started_at") or "").strip() or None
        latest_timestamp = str(state.get("log_updated_at") or "").strip() or None

        with CKPOOL_LOG_PATH.open("rb") as handle:
            handle.seek(offset)
            for raw_line in handle:
                line = raw_line.decode("utf-8", errors="replace")
                ts_match = _CKPOOL_LOG_TIMESTAMP_RE.match(line)
                line_timestamp = ts_match.group(1) if ts_match else latest_timestamp
                if line_timestamp:
                    first_log_timestamp = first_log_timestamp or line_timestamp
                    latest_timestamp = line_timestamp

                diff_match = _CKPOOL_NETWORK_DIFF_RE.search(line)
                if diff_match:
                    current_difficulty = _safe_float(diff_match.group(1))
                    continue

                runtime_match = _CKPOOL_RUNTIME_RE.search(line)
                if runtime_match:
                    current_runtime = _safe_int(runtime_match.group(1))

                accepted_match = _CKPOOL_ACCEPTED_RE.search(line)
                if not accepted_match:
                    continue
                accepted = _safe_int(accepted_match.group(1))
                if accepted is None:
                    continue

                if previous_accepted is not None and line_timestamp and line_timestamp >= anchor_log_time:
                    counter_reset = accepted < previous_accepted
                    if current_runtime is not None and previous_runtime is not None and current_runtime < previous_runtime:
                        counter_reset = True
                    if counter_reset:
                        counter_resets += 1
                    else:
                        delta = accepted - previous_accepted
                        if delta >= 0 and current_difficulty is not None and current_difficulty > 0:
                            effort += float(delta) / float(current_difficulty)
                            weighted_work += int(delta)
                            samples += 1
                        elif delta > 0:
                            skipped_samples += 1

                previous_accepted = accepted
                previous_runtime = current_runtime

            offset = int(handle.tell())

        live_accepted = _safe_int((pool_status or {}).get("accepted"))
        live_runtime = _safe_int((pool_status or {}).get("runtime"))
        live_difficulty = _safe_float(network_difficulty)
        if live_difficulty is None or live_difficulty <= 0:
            live_difficulty = current_difficulty
        if live_accepted is not None and previous_accepted is not None:
            counter_reset = live_accepted < previous_accepted
            if live_runtime is not None and previous_runtime is not None and live_runtime < previous_runtime:
                counter_reset = True
            if counter_reset:
                counter_resets += 1
            else:
                delta = live_accepted - previous_accepted
                if delta > 0 and live_difficulty is not None and live_difficulty > 0:
                    effort += float(delta) / float(live_difficulty)
                    weighted_work += int(delta)
                    samples += 1
                elif delta > 0:
                    skipped_samples += 1
            previous_accepted = live_accepted
            previous_runtime = live_runtime
        elif live_accepted is not None:
            previous_accepted = live_accepted
            previous_runtime = live_runtime
        if live_difficulty is not None and live_difficulty > 0:
            current_difficulty = live_difficulty

        coverage_complete = bool(state.get("coverage_complete"))
        if full_replay:
            coverage_complete = bool(first_log_timestamp and first_log_timestamp <= anchor_log_time and skipped_samples == 0)

        state.update(
            {
                "version": 1,
                "anchor_at": anchor_t,
                "anchor_hash": anchor_hash,
                "anchor_source": anchor_source,
                "anchor_log_time": anchor_log_time,
                "effort": effort,
                "luck_pct": effort * 100.0,
                "weighted_work": weighted_work,
                "samples": samples,
                "counter_resets": counter_resets,
                "skipped_samples": skipped_samples,
                "last_accepted": previous_accepted,
                "last_runtime": previous_runtime,
                "last_network_difficulty": current_difficulty,
                "log_offset": offset,
                "log_started_at": first_log_timestamp,
                "log_updated_at": latest_timestamp,
                "coverage_complete": coverage_complete,
                "rebuilding": False,
                "error": None,
                "updated_at": int(time.time()),
            }
        )
        _write_json_file(ROUND_EFFORT_STATE_PATH, state)
        return state
    finally:
        _ROUND_EFFORT_UPDATE_LOCK.release()


def _current_round_payload(
    *,
    pool_state: dict | None = None,
    events: list[dict] | None = None,
    network_difficulty: float | None = None,
) -> dict:
    state = dict(pool_state) if isinstance(pool_state, dict) else _read_json_file(POOL_STATE_PATH)
    items = events if isinstance(events, list) else _snapshot_block_events()

    started_at = _safe_int(state.get("round_started_at")) or 0
    effort_state = _round_effort_snapshot(items)
    rebuilding_effort = bool(effort_state.get("rebuilding")) or not effort_state
    total_diff = None if rebuilding_effort else _safe_float(effort_state.get("weighted_work"))
    total_diff_source = "rebuilding" if rebuilding_effort else "difficulty-weighted-log"
    shares = _safe_int(state.get("round_shares"))

    net_diff = _safe_float(network_difficulty)
    if net_diff is None:
        try:
            net_diff = _safe_float(_node_status().get("difficulty"))
        except Exception:
            net_diff = None

    effort = None if rebuilding_effort else _safe_float(effort_state.get("effort"))

    newest = items[0] if items else {}
    last_block_t = _safe_int((newest or {}).get("t")) if isinstance(newest, dict) else 0
    since_anchor = last_block_t if last_block_t and last_block_t > 0 else started_at
    since_seconds = max(0, int(time.time()) - int(since_anchor)) if since_anchor > 0 else 0

    return {
        "effort": effort,
        "luckPct": effort * 100.0 if effort is not None else None,
        "expectedPct": 100.0,
        "started": _iso_utc(started_at),
        "trackedSince": _iso_utc(started_at),
        "sinceSeconds": since_seconds,
        "lastBlockTime": newest.get("foundAt") if isinstance(newest, dict) else None,
        "lastBlockHeight": _safe_int((newest or {}).get("height")) if isinstance(newest, dict) else None,
        "lastBlockHash": str((newest or {}).get("hash") or "").strip() if isinstance(newest, dict) else "",
        "lastBlockMiner": str((newest or {}).get("miner") or "").strip() if isinstance(newest, dict) else "",
        "totalDiff": total_diff,
        "totalDiffSource": total_diff_source,
        "shares": shares,
        "networkDifficulty": net_diff,
        "effortCoverageComplete": bool(effort_state.get("coverage_complete")),
        "effortRebuilding": rebuilding_effort,
        "effortUpdatedAt": _safe_int(effort_state.get("updated_at")),
        "counterResets": _safe_int(effort_state.get("counter_resets")) or 0,
    }


def _luck_api() -> dict:
    events = _snapshot_block_events()
    recent = events[:5]
    current = _current_round_payload(events=events)
    luck_values = []
    for event in recent:
        value = _safe_float(event.get("luck_pct") if event.get("luck_pct") is not None else event.get("luckPct"))
        if value is not None:
            luck_values.append(value)
    summary = {
        "blocks": len(recent),
        "averageLuckPct": (sum(luck_values) / len(luck_values)) if luck_values else None,
        "bestLuckPct": min(luck_values) if luck_values else None,
        "worstLuckPct": max(luck_values) if luck_values else None,
    }
    return {
        "current": current,
        "recent": recent,
        "summary": summary,
    }


def _estimate_time_to_block_seconds(network_difficulty: float | None, hashrate_ths: float | None) -> float | None:
    try:
        if network_difficulty is None or hashrate_ths is None:
            return None
        diff = float(network_difficulty)
        ths = float(hashrate_ths)
        if not math.isfinite(diff) or not math.isfinite(ths) or diff <= 0 or ths <= 0:
            return None
        hps = ths * 1e12
        return (diff * 4294967296.0) / hps
    except Exception:
        return None


def _pool_api():
    pool = _parse_pool_status(_read_pool_status_raw())

    user = {}
    try:
        user = _read_ckpool_user_stats()
    except Exception:
        user = {}
    active_summary = _active_worker_summary(user)

    best_share_user = _best_share_int(user.get("bestshare")) if isinstance(user, dict) else None
    best_ever_user = _best_share_int(user.get("bestever")) if isinstance(user, dict) else None

    best_share = best_share_user if best_share_user is not None else _best_share_int(pool.get("best_share"))
    if best_share is not None and int(best_share) <= 0:
        best_share = None
    pool["best_share"] = best_share
    state = _read_json_file(POOL_STATE_PATH)
    best_all_time = _best_share_int(state.get("best_share_all_time"))

    # Prefer ckpool's per-user "bestever" if available.
    if best_ever_user is not None and (best_all_time is None or best_ever_user > best_all_time):
        best_all_time = best_ever_user
        state["best_share_all_time"] = best_all_time
        state["best_share_all_time_at"] = int(time.time())
        _write_json_file(POOL_STATE_PATH, state)

    if best_share is not None and (best_all_time is None or best_share > best_all_time):
        best_all_time = best_share
        state["best_share_all_time"] = best_all_time
        state["best_share_all_time_at"] = int(time.time())
        _write_json_file(POOL_STATE_PATH, state)

    pool["best_share_all_time"] = best_all_time

    if isinstance(active_summary, dict):
        pool["workers"] = int(active_summary.get("active_workers") or 0)
        pool["active_workers"] = int(active_summary.get("active_workers") or 0)
        pool["seen_workers"] = int(active_summary.get("seen_workers") or 0)

        hashrates = dict(pool.get("hashrates_ths") or {}) if isinstance(pool.get("hashrates_ths"), dict) else {}
        active_hashrates = active_summary.get("hashrates_ths")
        if isinstance(active_hashrates, dict):
            hashrates.update(active_hashrates)
        pool["hashrates_ths"] = hashrates
        pool["hashrate_ths"] = float(active_summary.get("hashrate_ths") or 0.0)

    try:
        since_best = _best_share_int(state.get("since_block_best_share"))
    except Exception:
        since_best = None
    since_worker = str(state.get("since_block_best_share_worker") or "").strip() or None
    pool["best_share_since_block"] = since_best if since_best is not None and since_best > 0 else None
    pool["best_share_since_block_worker"] = since_worker

    # Reset "Since block" right after a solve so it only reflects shares submitted after the solve.
    # ckpool's per-user bestshare may still show the winning share until the next share updates stats.
    try:
        last_solve_at = int(state.get("last_solve_at") or 0)
    except Exception:
        last_solve_at = 0
    try:
        user_lastshare = int(float(user.get("lastshare") or 0)) if isinstance(user, dict) else 0
    except Exception:
        user_lastshare = 0
    if last_solve_at > 0 and (user_lastshare <= 0 or user_lastshare <= last_solve_at):
        pool["best_share"] = None
        pool["best_share_reset_at"] = last_solve_at

    try:
        node = _node_status()
        net_diff = node.get("difficulty")
        net_height = node.get("blocks")
        node_ibd = bool(node.get("initialblockdownload"))
        node_template_ready = node.get("template_ready")
        node_template_error = str(node.get("template_error") or "").strip() or None
        node_template_error_code = node.get("template_error_code")
    except Exception:
        net_diff = None
        net_height = None
        node_ibd = True
        node_template_ready = None
        node_template_error = None
        node_template_error_code = None

    # ckpool can report a 0 1m rate even while longer windows are non-zero. Use
    # the first non-zero window so ETA + headline hashrate stay meaningful.
    try:
        hashrate_ths = pool.get("hashrate_ths")
        hashrate_f = float(hashrate_ths) if hashrate_ths is not None else None
    except Exception:
        hashrate_f = None

    hashrates = pool.get("hashrates_ths") if isinstance(pool.get("hashrates_ths"), dict) else {}
    if not isinstance(hashrates, dict):
        hashrates = {}

    chosen_window = None
    if hashrate_f is None or hashrate_f <= 0:
        for k in ["5m", "15m", "1h", "6h", "1d", "7d", "1m"]:
            v = hashrates.get(k)
            try:
                fv = float(v)
            except Exception:
                continue
            if math.isfinite(fv) and fv > 0:
                hashrate_f = fv
                chosen_window = k
                break

    if hashrate_f is not None and math.isfinite(hashrate_f):
        pool["hashrate_ths"] = hashrate_f
    else:
        pool["hashrate_ths"] = None

    if chosen_window:
        pool["hashrate_window"] = chosen_window

    eta_seconds = _estimate_time_to_block_seconds(net_diff, pool.get("hashrate_ths"))
    pool["network_difficulty"] = net_diff
    pool["network_height"] = net_height
    pool["network_algo"] = "sha256d"
    pool["eta_seconds"] = eta_seconds
    pool["eta_text"] = _format_duration(eta_seconds)

    block_events = _snapshot_block_events()
    pool.update(_block_summary_from_events(block_events))
    pool["current_round"] = _current_round_payload(
        pool_state=state,
        events=block_events,
        network_difficulty=_safe_float(net_diff),
    )

    pool_settings = _pool_settings()
    pool["pool_settings"] = pool_settings
    pool["backend_ready"] = not (node_template_ready is False)
    if node_template_ready is False:
        if node_template_error_code == -9:
            pool["backend_reason"] = "BCH node RPC is up, but the node is not mining-ready yet. Waiting for block templates."
        elif node_template_error:
            pool["backend_reason"] = f"BCH node is reachable, but block template generation is failing: {node_template_error}"
        else:
            pool["backend_reason"] = "BCH node is reachable, but block template generation is not ready yet."
    else:
        pool["backend_reason"] = "Pool backend is online."
    pool["stratum"] = _stratum_status(
        configured=bool(pool_settings.get("configured")),
        node_ibd=node_ibd,
        node_template_ready=node_template_ready,
        node_template_error=node_template_error,
        node_template_error_code=node_template_error_code,
        workers=pool.get("workers"),
        hashrate_ths=pool.get("hashrate_ths"),
        accepted=pool.get("accepted"),
    )
    return pool


def _stratum_status(
    *,
    configured: bool,
    node_ibd: bool,
    node_template_ready=None,
    node_template_error=None,
    node_template_error_code=None,
    workers=None,
    hashrate_ths=None,
    accepted=None,
) -> dict:
    if not configured:
        return {
            "status": "locked",
            "reason": "Set a BCH payout address in Settings, then restart Curtis BCH.",
        }
    try:
        workers_i = int(workers or 0)
    except Exception:
        workers_i = 0
    try:
        accepted_i = int(accepted or 0)
    except Exception:
        accepted_i = 0
    try:
        hashrate_f = float(hashrate_ths or 0)
    except Exception:
        hashrate_f = 0.0
    if workers_i > 0 or accepted_i > 0 or (math.isfinite(hashrate_f) and hashrate_f > 0):
        return {
            "status": "open",
            "reason": "Remote miners can connect.",
        }
    if node_ibd:
        return {
            "status": "locked",
            "reason": "Wait for the BCH node to finish syncing before opening Stratum.",
        }
    if node_template_ready is False:
        if node_template_error_code == -9:
            return {
                "status": "locked",
                "reason": "BCH has peers, but is not returning mining templates yet. Wait for the node to become mining-ready.",
            }
        return {
            "status": "locked",
            "reason": (
                f"BCH is reachable, but block templates are failing: {node_template_error}"
                if node_template_error
                else "BCH is reachable, but block templates are not ready yet."
            ),
        }
    try:
        with socket.create_connection((CKPOOL_STRATUM_HOST, CKPOOL_STRATUM_PORT), timeout=1.5):
            return {
                "status": "open",
                "reason": "Remote miners can connect.",
            }
    except Exception:
        return {
            "status": "locked",
            "reason": "Pool backend is still bringing Stratum online. Retry in a few seconds.",
        }


def _read_ckpool_user_stats() -> dict:
    try:
        conf = _read_ckpool_conf()
        user = str(conf.get("btcaddress") or "").strip()
    except Exception:
        user = ""

    return read_merged_user_stats(CKPOOL_USERS_DIR, user, _to_hashrate_ths)


def _pool_workers_api() -> dict:
    now = int(time.time())
    user = _read_ckpool_user_stats()
    active_summary = _active_worker_summary(user, now_s=now)
    worker_rows = user.get("worker") if isinstance(user.get("worker"), list) else []
    pool_state = _read_json_file(POOL_STATE_PATH)
    by_worker = pool_state.get("since_block_best_share_by_worker") if isinstance(pool_state, dict) else None
    if not isinstance(by_worker, dict):
        by_worker = {}
    last_by_worker = pool_state.get("last_share_diff_by_worker") if isinstance(pool_state, dict) else None
    if not isinstance(last_by_worker, dict):
        last_by_worker = {}

    # Keep the per-worker "best since block" consistent with the overall card.
    # Older installs may have a correct overall best value but an incomplete
    # per-worker map (added later), which makes the worker list look "too low".
    since_block_best_i = None
    since_block_best_worker = ""
    since_block_best_worker_suffix = ""
    since_block_tracker_started = False
    if isinstance(pool_state, dict):
        since_block_tracker_started = (_safe_int(pool_state.get("since_block_started_at")) or 0) > 0
        since_block_best_i = _best_share_int(pool_state.get("since_block_best_share"))
        since_block_best_worker = str(pool_state.get("since_block_best_share_worker") or "").strip()
        since_block_best_worker_suffix = since_block_best_worker.split(".")[-1].strip() if "." in since_block_best_worker else since_block_best_worker

    def _maybe_int(v):
        try:
            if v is None or isinstance(v, bool):
                return None
            if isinstance(v, int):
                return int(v)
            if isinstance(v, float):
                if not math.isfinite(v):
                    return None
                return int(v)
            s = str(v).strip()
            if not s:
                return None
            if re.fullmatch(r"[0-9]+", s):
                return int(s)
            # tolerate "123.0"
            f = float(s)
            if not math.isfinite(f):
                return None
            return int(f)
        except Exception:
            return None

    workers = []
    for w in worker_rows:
        if not isinstance(w, dict):
            continue
        name = str(w.get("workername") or "").strip()
        # ckpool reports workers as "<payout>.<worker>", but the UI and the
        # sharelog-derived "best share since block" tracker operate on the
        # worker suffix. Try both forms so the UI can show per-worker best
        # share even when ckpool includes the payout prefix.
        name_suffix = name.split(".")[-1].strip() if "." in name else name
        lastshare = w.get("lastshare")
        try:
            lastshare_i = int(float(lastshare)) if lastshare is not None else None
        except Exception:
            lastshare_i = None
        bestshare_i = _best_share_int(w.get("bestshare"))
        if bestshare_i is not None and bestshare_i <= 0:
            bestshare_i = None

        bestshare_since_block_i = None
        if name or name_suffix:
            try:
                bestshare_since_block_i = _best_share_int(by_worker.get(name_suffix) or by_worker.get(name))
                if bestshare_since_block_i is not None and bestshare_since_block_i <= 0:
                    bestshare_since_block_i = None
            except Exception:
                bestshare_since_block_i = None

        # If this worker is the overall "best since block" winner, ensure the per-worker
        # value is at least the overall best.
        if since_block_best_i is not None and since_block_best_i > 0 and (name or name_suffix):
            if (since_block_best_worker and name == since_block_best_worker) or (
                since_block_best_worker_suffix and name_suffix == since_block_best_worker_suffix
            ):
                if bestshare_since_block_i is None or bestshare_since_block_i < since_block_best_i:
                    bestshare_since_block_i = since_block_best_i

        # ckpool's bestshare is all-time and cannot be used as a since-block
        # fallback once the period tracker exists. Doing so made manual resets
        # and post-block resets appear to fail.
        if not since_block_tracker_started and bestshare_i is not None and (
            bestshare_since_block_i is None or bestshare_since_block_i < bestshare_i
        ):
            bestshare_since_block_i = bestshare_i

        current_diff_i = None
        for k in ["difficulty", "diff", "curdiff", "currentdiff", "vardiff", "stratumDifficulty"]:
            current_diff_i = _maybe_int(w.get(k))
            if current_diff_i is not None and current_diff_i > 0:
                break
            current_diff_i = None
        if current_diff_i is None and name_suffix:
            try:
                v = _best_share_int(last_by_worker.get(name_suffix))
            except Exception:
                v = None
            if v is not None and v > 0:
                current_diff_i = int(v)

        workers.append(
            {
                "workername": name,
                "hashrate_ths": _to_hashrate_ths(w.get("hashrate1m")),
                "hashrate_1m_ths": _to_hashrate_ths(w.get("hashrate1m")),
                "hashrate_5m_ths": _to_hashrate_ths(w.get("hashrate5m")),
                "hashrate_15m_ths": _to_hashrate_ths(w.get("hashrate15m")),
                "hashrate_1h_ths": _to_hashrate_ths(w.get("hashrate1hr") or w.get("hashrate1h")),
                "hashrate_6h_ths": _to_hashrate_ths(w.get("hashrate6hr") or w.get("hashrate6h")),
                "hashrate_1d_ths": _to_hashrate_ths(w.get("hashrate1d")),
                "hashrate_7d_ths": _to_hashrate_ths(w.get("hashrate7d")),
                "lastshare": lastshare_i,
                "lastshare_ago_s": (now - lastshare_i) if lastshare_i else None,
                "shares": int(float(w.get("shares") or 0)),
                "bestshare": bestshare_i,
                "bestever": _best_share_int(w.get("bestever")),
                "bestshare_since_block": bestshare_since_block_i,
                "current_diff": current_diff_i,
            }
        )

    workers.sort(key=lambda x: int(x.get("lastshare") or 0), reverse=True)

    try:
        user_lastshare = int(float(user.get("lastshare") or 0)) if user.get("lastshare") is not None else None
    except Exception:
        user_lastshare = None

    try:
        worker_count = int(float(user.get("workers"))) if user.get("workers") is not None else len(workers)
    except Exception:
        worker_count = len(workers)

    return {
        "workers": worker_count,
        "active_workers": int(active_summary.get("active_workers") or 0) if isinstance(active_summary, dict) else 0,
        "seen_workers": int(active_summary.get("seen_workers") or 0) if isinstance(active_summary, dict) else 0,
        "active_hashrate_ths": float(active_summary.get("hashrate_ths") or 0.0) if isinstance(active_summary, dict) else 0.0,
        "lastshare": user_lastshare,
        "lastshare_ago_s": (now - user_lastshare) if user_lastshare else None,
        "workers_details": workers,
    }


def _scan_ckpool_log_for_block_events() -> None:
    # Best-effort: tail ckpool log for block solve/submit messages.
    try:
        if not (CKPOOL_LOG_PATH.exists() and CKPOOL_LOG_PATH.is_file()):
            return
    except Exception:
        return

    state = _read_json_file(CKPOOL_LOG_STATE_PATH)
    try:
        offset = int(state.get("offset") or 0)
    except Exception:
        offset = 0

    try:
        size = int(CKPOOL_LOG_PATH.stat().st_size)
    except Exception:
        return

    if offset > size:
        offset = 0

    try:
        with CKPOOL_LOG_PATH.open("rb") as f:
            f.seek(offset)
            chunk = f.read()
            new_offset = f.tell()
    except Exception:
        return

    if not chunk:
        return

    text = chunk.decode("utf-8", errors="replace")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    block_re = re.compile(r"(?i)\b([0-9a-f]{64})\b")
    trigger_re = re.compile(r"(?i)\b(solved|block found|found a block|submitblock|submitted block)\b")
    ignore_re = re.compile(r"(?i)\b(zmq block hash|block hash changed)\b")

    blocks_state = _read_json_file(BLOCKS_STATE_PATH)
    events = blocks_state.get("events") if isinstance(blocks_state.get("events"), list) else []
    known = {e.get("hash") for e in events if isinstance(e, dict)}
    pool_state = _read_json_file(POOL_STATE_PATH)
    try:
        net_diff = _safe_float(_node_status().get("difficulty"))
    except Exception:
        net_diff = None

    last_solve_now = None
    for ln in lines:
        if ignore_re.search(ln):
            continue
        if not trigger_re.search(ln):
            continue
        m = block_re.search(ln)
        if not m:
            continue
        h = m.group(1).lower()
        if h in known:
            continue
        now_s = int(time.time())
        solve_diff = _safe_float(pool_state.get("since_block_best_share"))
        solve_worker = str(pool_state.get("since_block_best_share_worker") or "").strip() or None
        round_total = _safe_int(pool_state.get("round_total_diff")) or 0
        round_shares = _safe_int(pool_state.get("round_shares")) or 0
        round_effort = None
        if net_diff is not None and net_diff > 0 and round_total > 0:
            round_effort = float(round_total) / float(net_diff)

        event = {"t": now_s, "detected_at": now_s, "hash": h, "log": ln, "source": "ckpool"}
        if net_diff is not None and net_diff > 0:
            event["network_difficulty"] = float(net_diff)
        if solve_diff is not None and solve_diff > 0:
            event["solve_diff"] = float(solve_diff)
        if solve_worker:
            event["solve_worker"] = solve_worker
        if round_total > 0:
            event["round_total_diff"] = int(round_total)
            event["round_shares"] = int(round_shares)
        if round_effort is not None:
            event["round_effort"] = float(round_effort)
            event["luck_pct"] = float(round_effort) * 100.0

        events.append(event)
        known.add(h)
        last_solve_now = now_s

    blocks_state["events"] = events[-200:]
    _write_json_file(BLOCKS_STATE_PATH, blocks_state)
    _write_json_file(CKPOOL_LOG_STATE_PATH, {"offset": new_offset, "updated_at": int(time.time())})

    if last_solve_now:
        try:
            pool_state["last_solve_at"] = int(last_solve_now)
            # Auto-reset "Since block" on solve: suppress the current bestshare value.
            try:
                best = _best_share_int(pool_state.get("since_block_best_share"))
                _reset_since_block_best_share_tracker(
                    pool_state=pool_state,
                    started_at=int(last_solve_now),
                    exclude_value=int(best) if best is not None and best > 0 else None,
                    exclude_reason="block",
                    scan_from_start=False,
                    anchor_hash=str(pool_state.get("since_block_anchor_hash") or "").strip().lower() or None,
                )
            except Exception:
                pass
            _write_json_file(POOL_STATE_PATH, pool_state)
        except Exception:
            pass


def _ckpool_sharelog_paths(network_height: int | None = None, window: int = 12) -> list[Path]:
    root = CKPOOL_SHARELOG_ROOT
    out: list[Path] = []
    try:
        if not root.exists():
            return []

        height = _safe_int(network_height)
        if height is None or height <= 0:
            try:
                height = _safe_int(_node_status().get("blocks"))
            except Exception:
                height = None
        if height is None or height <= 0:
            return []

        # ckpool stores shares under hexadecimal block-height directories. Only
        # the current/recent jobs can receive new shares; walking every historic
        # directory made long-running nodes scan hundreds of thousands of files
        # and rewrite multi-megabyte offset maps every 30 seconds.
        start_height = max(0, int(height) - max(2, int(window)))
        directories = [root / f"{h:08x}" for h in range(start_height, int(height) + 2)]
        for d in directories:
            if not d.is_dir():
                continue
            for f in d.glob("*.sharelog"):
                if f.is_file():
                    out.append(f)
    except Exception:
        return []
    out.sort(key=lambda p: str(p))
    return out


def _ckpool_sharelog_offsets_at_end(network_height: int | None = None) -> dict[str, int]:
    offsets: dict[str, int] = {}
    for p in _ckpool_sharelog_paths(network_height=network_height):
        try:
            rel = str(p.relative_to(CKPOOL_SHARELOG_ROOT))
        except Exception:
            rel = str(p)
        try:
            offsets[rel] = int(p.stat().st_size)
        except Exception:
            continue
    return offsets


def _parse_sharelog_createdate_s(value) -> int | None:
    try:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        # Format: "1767712973,479418327"
        if "," in s:
            s = s.split(",", 1)[0]
        t = int(s)
        return t if t > 0 else None
    except Exception:
        return None


def _reset_since_block_best_share_tracker(
    *,
    pool_state: dict,
    started_at: int,
    exclude_value: int | None,
    exclude_reason: str,
    scan_from_start: bool,
    anchor_hash: str | None = None,
) -> None:
    pool_state["since_block_started_at"] = int(started_at)
    pool_state["since_block_best_share"] = None
    pool_state["since_block_best_share_worker"] = None
    pool_state["since_block_best_share_at"] = None
    pool_state["since_block_best_share_by_worker"] = {}
    pool_state["since_block_sharelog_offsets"] = {} if scan_from_start else _ckpool_sharelog_offsets_at_end()
    pool_state["since_block_sharelog_set_at"] = int(started_at)
    pool_state["since_block_anchor_at"] = int(started_at)
    pool_state["since_block_anchor_hash"] = str(anchor_hash or "").strip().lower() or None

    try:
        pool_state["since_block_log_offset"] = int(CKPOOL_LOG_PATH.stat().st_size)
    except Exception:
        pool_state["since_block_log_offset"] = 0

    if exclude_value is not None and exclude_value > 0:
        pool_state["since_block_exclude_value"] = int(exclude_value)
        pool_state["since_block_exclude_set_at"] = int(started_at)
        pool_state["since_block_exclude_reason"] = str(exclude_reason or "").strip() or "unknown"
    else:
        pool_state["since_block_exclude_value"] = None
        pool_state["since_block_exclude_set_at"] = None
        pool_state["since_block_exclude_reason"] = None


def _reset_round_tracker(
    *,
    pool_state: dict,
    started_at: int,
    scan_from_start: bool,
    anchor_hash: str | None = None,
) -> None:
    pool_state["round_started_at"] = int(started_at)
    pool_state["round_total_diff"] = 0
    pool_state["round_shares"] = 0
    pool_state["round_total_diff_at"] = int(started_at)
    pool_state["round_sharelog_offsets"] = {} if scan_from_start else _ckpool_sharelog_offsets_at_end()
    pool_state["round_sharelog_set_at"] = int(started_at)
    pool_state["round_anchor_at"] = int(started_at)
    pool_state["round_anchor_hash"] = str(anchor_hash or "").strip().lower() or None


def _latest_block_event_anchor(events: list[dict] | None = None) -> dict | None:
    items = events if isinstance(events, list) else _snapshot_block_events()
    if not items:
        return None
    newest = items[0] if isinstance(items[0], dict) else None
    if not isinstance(newest, dict):
        return None
    anchor_t = _safe_int(newest.get("t")) or 0
    if anchor_t <= 0:
        return None
    anchor_hash = str(newest.get("hash") or "").strip().lower() or None
    return {"t": int(anchor_t), "hash": anchor_hash}


def _sync_trackers_to_latest_block_event(events: list[dict] | None = None) -> bool:
    anchor = _latest_block_event_anchor(events)
    if not anchor:
        return False

    try:
        state = _read_json_file(POOL_STATE_PATH)
    except Exception:
        state = {}

    anchor_t = int(anchor.get("t") or 0)
    anchor_hash = str(anchor.get("hash") or "").strip().lower() or None
    if anchor_t <= 0:
        return False

    changed = False

    best_started_at = _safe_int(state.get("since_block_started_at")) or 0
    best_anchor_at = _safe_int(state.get("since_block_anchor_at")) or 0
    best_anchor_hash = str(state.get("since_block_anchor_hash") or "").strip().lower() or None
    need_best_reset = (
        best_started_at <= 0
        or best_anchor_at <= 0
        or best_anchor_at < anchor_t
        or (anchor_hash and anchor_hash != best_anchor_hash)
    )
    if need_best_reset:
        _reset_since_block_best_share_tracker(
            pool_state=state,
            started_at=anchor_t,
            exclude_value=None,
            exclude_reason="block",
            scan_from_start=True,
            anchor_hash=anchor_hash,
        )
        changed = True

    round_started_at = _safe_int(state.get("round_started_at")) or 0
    round_anchor_at = _safe_int(state.get("round_anchor_at")) or 0
    round_anchor_hash = str(state.get("round_anchor_hash") or "").strip().lower() or None
    need_round_reset = (
        round_started_at <= 0
        or round_anchor_at <= 0
        or round_anchor_at < anchor_t
        or (anchor_hash and anchor_hash != round_anchor_hash)
    )
    if need_round_reset:
        _reset_round_tracker(
            pool_state=state,
            started_at=anchor_t,
            scan_from_start=True,
            anchor_hash=anchor_hash,
        )
        changed = True

    if changed:
        _write_json_file(POOL_STATE_PATH, state)
    return changed


def _scan_ckpool_sharelogs_for_trackers(network_height: int | None = None) -> None:
    try:
        state = _read_json_file(POOL_STATE_PATH)
    except Exception:
        state = {}

    try:
        best_started_at = int(state.get("since_block_started_at") or 0)
    except Exception:
        best_started_at = 0
    try:
        round_started_at = int(state.get("round_started_at") or 0)
    except Exception:
        round_started_at = 0
    if best_started_at <= 0 and round_started_at <= 0:
        return

    best_positions = state.get("since_block_sharelog_offsets")
    if not isinstance(best_positions, dict):
        best_positions = {}
    round_positions = state.get("round_sharelog_offsets")
    if not isinstance(round_positions, dict):
        round_positions = {}

    try:
        best_exclude_val = _best_share_int(state.get("since_block_exclude_value"))
    except Exception:
        best_exclude_val = None

    try:
        best = _best_share_int(state.get("since_block_best_share"))
    except Exception:
        best = None
    best_worker = str(state.get("since_block_best_share_worker") or "").strip() or None
    by_worker = state.get("since_block_best_share_by_worker")
    if not isinstance(by_worker, dict):
        by_worker = {}
    by_worker_updated = False

    last_diff_by_worker = state.get("last_share_diff_by_worker")
    if not isinstance(last_diff_by_worker, dict):
        last_diff_by_worker = {}
    last_at_by_worker = state.get("last_share_at_by_worker")
    if not isinstance(last_at_by_worker, dict):
        last_at_by_worker = {}
    total_diff = _safe_int(state.get("round_total_diff")) or 0
    share_count = _safe_int(state.get("round_shares")) or 0
    round_updated = False

    sharelogs = _ckpool_sharelog_paths(network_height=network_height)
    existing = {str(p.relative_to(CKPOOL_SHARELOG_ROOT)) for p in sharelogs}
    best_positions = {k: v for (k, v) in best_positions.items() if k in existing}
    round_positions = {k: v for (k, v) in round_positions.items() if k in existing}

    def _read_sharelog_entries(path: Path, rel: str, offset_map: dict) -> tuple[list[tuple[int, int, int, str | None]], int]:
        try:
            offset = int(offset_map.get(rel) or 0)
        except Exception:
            offset = 0

        try:
            size = int(path.stat().st_size)
        except Exception:
            return [], offset
        if offset > size:
            offset = 0

        max_read = 2_000_000
        if size - offset > max_read:
            offset = max(0, size - max_read)

        try:
            with path.open("rb") as f:
                f.seek(offset)
                chunk = f.read()
                new_offset = f.tell()
        except Exception:
            return [], offset

        if not chunk:
            return [], int(new_offset)

        out: list[tuple[int, int, int, str | None]] = []
        for raw in chunk.splitlines():
            if not raw:
                continue
            try:
                obj = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue

            ts_s = _parse_sharelog_createdate_s(obj.get("createdate")) or 0
            effective_ts = ts_s if ts_s > 0 else int(time.time())
            diff_i = _best_share_int(obj.get("sdiff"))
            if diff_i is None:
                diff_i = _best_share_int(obj.get("diff"))
            if diff_i is None or diff_i <= 0:
                continue

            w = str(obj.get("workername") or "").strip() or None
            if w and "." in w:
                w = w.split(".")[-1].strip() or w
            out.append((ts_s, effective_ts, int(diff_i), w))

        return out, int(new_offset)

    best_updated = False
    for p in sharelogs:
        try:
            rel = str(p.relative_to(CKPOOL_SHARELOG_ROOT))
        except Exception:
            rel = str(p)

        best_entries, best_new_offset = _read_sharelog_entries(p, rel, best_positions)
        best_positions[rel] = int(best_new_offset)
        for ts_s, _effective_ts, diff_i, w in best_entries:
            if ts_s > 0 and ts_s <= best_started_at:
                continue
            if best_exclude_val is not None and int(diff_i) == int(best_exclude_val):
                continue

            if best is None or diff_i > best:
                best = diff_i
                best_worker = w
                best_updated = True

            if w:
                try:
                    prev = _best_share_int(by_worker.get(w))
                except Exception:
                    prev = None
                if prev is None or diff_i > prev:
                    by_worker[w] = int(diff_i)
                    by_worker_updated = True

        round_entries, round_new_offset = _read_sharelog_entries(p, rel, round_positions)
        round_positions[rel] = int(round_new_offset)
        for ts_s, effective_ts, diff_i, w in round_entries:
            if w:
                try:
                    prev_ts = int(float(last_at_by_worker.get(w) or 0))
                except Exception:
                    prev_ts = 0
                if prev_ts <= 0 or effective_ts >= prev_ts:
                    last_at_by_worker[w] = int(effective_ts)
                    last_diff_by_worker[w] = int(diff_i)

            if ts_s > 0 and ts_s <= round_started_at:
                continue

            total_diff += int(diff_i)
            share_count += 1
            round_updated = True

    state["since_block_sharelog_offsets"] = best_positions
    state["round_sharelog_offsets"] = round_positions
    state["last_share_diff_by_worker"] = last_diff_by_worker
    state["last_share_at_by_worker"] = last_at_by_worker
    if round_updated:
        state["round_total_diff"] = int(total_diff)
        state["round_shares"] = int(share_count)
        state["round_total_diff_at"] = int(time.time())
    if by_worker_updated:
        state["since_block_best_share_by_worker"] = by_worker
    if best_updated:
        state["since_block_best_share"] = int(best) if best is not None else None
        state["since_block_best_share_worker"] = best_worker
        state["since_block_best_share_at"] = int(time.time())
    _write_json_file(POOL_STATE_PATH, state)


def _ensure_trackers_initialized() -> None:
    now_s = int(time.time())
    try:
        state = _read_json_file(POOL_STATE_PATH)
    except Exception:
        state = {}

    try:
        best_started_at = int(state.get("since_block_started_at") or 0)
    except Exception:
        best_started_at = 0
    try:
        round_started_at = int(state.get("round_started_at") or 0)
    except Exception:
        round_started_at = 0

    if best_started_at > 0 and round_started_at > 0:
        return

    anchor = _latest_block_event_anchor()
    if anchor:
        anchor_t = int(anchor.get("t") or 0)
        anchor_hash = str(anchor.get("hash") or "").strip().lower() or None
    else:
        anchor_t = now_s
        anchor_hash = None

    if best_started_at <= 0:
        _reset_since_block_best_share_tracker(
            pool_state=state,
            started_at=anchor_t,
            exclude_value=None,
            exclude_reason="boot",
            scan_from_start=bool(anchor_hash),
            anchor_hash=anchor_hash,
        )
    if round_started_at <= 0:
        _reset_round_tracker(
            pool_state=state,
            started_at=anchor_t,
            scan_from_start=bool(anchor_hash),
            anchor_hash=anchor_hash,
        )
    _write_json_file(POOL_STATE_PATH, state)


def _reset_since_block_tracker_for_worker(worker: str) -> dict:
    raw = str(worker or "").strip()
    if not raw:
        raise ValueError("missing worker")

    name = raw
    name_suffix = raw.split(".")[-1].strip() if "." in raw else raw

    state = _read_json_file(POOL_STATE_PATH)
    if not isinstance(state, dict):
        state = {}

    by_worker = state.get("since_block_best_share_by_worker")
    if not isinstance(by_worker, dict):
        by_worker = {}

    removed = []
    for k in [name, name_suffix]:
        if not k:
            continue
        if k in by_worker:
            removed.append(k)
            by_worker.pop(k, None)

    # Recompute the overall "since block" best from the remaining per-worker map.
    best_val = None
    best_key = None
    for k, v in by_worker.items():
        vi = _best_share_int(v)
        if vi is None or vi <= 0:
            continue
        if best_val is None or vi > best_val:
            best_val = int(vi)
            best_key = str(k)

    if best_val is None:
        state["since_block_best_share"] = None
        state["since_block_best_share_worker"] = None
        state["since_block_best_share_at"] = None
    else:
        state["since_block_best_share"] = int(best_val)
        state["since_block_best_share_worker"] = best_key
        state["since_block_best_share_at"] = int(time.time())

    state["since_block_best_share_by_worker"] = by_worker
    _write_json_file(POOL_STATE_PATH, state)

    _patch_bestshare_caches(
        reset_worker=name_suffix or name,
        best_share_since_block=best_val,
        best_share_since_block_worker=best_key,
    )

    return {
        "ok": True,
        "worker": name_suffix or name,
        "removedKeys": removed,
        "bestShareSinceBlock": best_val,
        "bestShareSinceBlockWorker": best_key,
    }


def _blocks_api() -> dict:
    state = _read_json_file(BLOCKS_STATE_PATH)
    events = state.get("events") if isinstance(state.get("events"), list) else []
    addrs = _payout_history_addresses()
    best_share = None
    best_worker = None
    try:
        for a in addrs:
            d, w = _ckpool_user_best_share(a)
            if d is None:
                continue
            if best_share is None or d > best_share:
                best_share = d
                best_worker = w
    except Exception:
        best_share = None
        best_worker = None
    out = []
    updated = False
    for e in events:
        if not isinstance(e, dict):
            continue
        h = str(e.get("hash") or "").strip().lower()
        if not re.match(r"^[0-9a-f]{64}$", h):
            continue

        # Opportunistically enrich events with metadata (txindex not required).
        if (
            not e.get("height")
            or not e.get("coinbase_txid")
            or e.get("confirmations") is None
            or e.get("network_difficulty") is None
            or e.get("solve_diff") is None
            or e.get("solve_worker") is None
        ):
            try:
                blk = _rpc_call("getblock", [h, 1])
                if isinstance(blk, dict):
                    height = blk.get("height")
                    txs = blk.get("tx")
                    coinbase_txid = txs[0] if isinstance(txs, list) and txs else None
                    block_time = blk.get("time")
                    if height is not None:
                        e["height"] = int(height)
                        updated = True
                    if block_time is not None:
                        try:
                            e["t"] = int(block_time)
                            updated = True
                        except Exception:
                            pass
                    if coinbase_txid:
                        e["coinbase_txid"] = str(coinbase_txid)
                        updated = True
                    if e.get("network_difficulty") is None and "difficulty" in blk and blk.get("difficulty") is not None:
                        try:
                            nd = float(blk.get("difficulty"))
                            if math.isfinite(nd) and nd > 0:
                                e["network_difficulty"] = nd
                                updated = True
                        except Exception:
                            pass
                    if "confirmations" in blk and blk.get("confirmations") is not None:
                        try:
                            e["confirmations"] = int(blk.get("confirmations"))
                            updated = True
                        except Exception:
                            pass
                    if e.get("solve_diff") is None and best_share is not None:
                        e["solve_diff"] = float(best_share)
                        updated = True
                    if e.get("solve_worker") is None and best_worker:
                        e["solve_worker"] = str(best_worker)
                        updated = True
            except Exception:
                pass

        normalized = _normalize_block_event(e)
        if normalized:
            out.append(normalized)
    out.sort(key=lambda x: int(x.get("t") or 0), reverse=True)
    if updated:
        state["events"] = events[-200:]
        _write_json_file(BLOCKS_STATE_PATH, state)
    backscan = state.get("backscan") if isinstance(state.get("backscan"), dict) else {}
    return {"events": out, "backscan": backscan}



def _request_ipv4(handler) -> str | None:
    try:
        host = str(handler.headers.get("Host") or "").strip()
        if host.startswith("["):
            return None
        host_only = host.rsplit(":", 1)[0] if ":" in host else host
        socket.inet_aton(host_only)
        if host_only.count(".") == 3 and not host_only.startswith("127."):
            return host_only
    except Exception:
        pass
    try:
        host = str(handler.headers.get("Host") or "").strip()
        host_only = host.rsplit(":", 1)[0] if ":" in host else host
        resolved = socket.gethostbyname(host_only)
        socket.inet_aton(resolved)
        if not resolved.startswith("127.") and not resolved.startswith("10.21."):
            return resolved
    except Exception:
        pass
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = f"{APP_ID}/{APP_VERSION}"

    def _send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/about":
            return self._send(*_json(_about()))

        if self.path == "/api/connect-info":
            pool = _pool_settings()
            node_chain = None
            try:
                node_chain = (_node_status() or {}).get("chain")
            except Exception:
                pass
            return self._send(*_json({
                "ipv4": _request_ipv4(self),
                "stratumPort": 6387,
                "payoutAddress": pool.get("payoutAddress"),
                "configured": bool(pool.get("configured")),
                "chain": node_chain,
                "network": _current_settings().get("network"),
            }))

        if self.path == "/api/settings":
            current = _current_settings()
            try:
                prune = int(body.get("prune", current.get("prune", 5500)))
            except Exception:
                return self._send(*_json({"error": "invalid prune"}, status=400))
            if prune != 0 and prune < 550:
                return self._send(*_json({"error": "prune must be 0 or >= 550 MiB"}, status=400))

            network = str(body.get("network", current.get("network", "mainnet")) or "mainnet").strip().lower()
            if network not in ("mainnet", "testnet4"):
                return self._send(*_json({"error": "network must be mainnet or testnet4"}, status=400))

            try:
                _update_prune_conf(prune)
                _update_network_conf(network)
            except Exception as e:
                return self._send(*_json({"error": str(e)}, status=400))

            return self._send(*_json({
                "ok": True,
                "settings": {"prune": prune, "network": network},
                "restartRequired": True,
                "networkChanged": network != current.get("network"),
            }))

        if self.path == "/api/pool/settings":
            return self._send(*_json(_pool_settings()))

        if self.path == "/api/support/status":
            return self._send(
                *_json(
                    {
                        "ticketEnabled": bool(SUPPORT_TICKET_URL),
                        "checkinEnabled": bool(SUPPORT_CHECKIN_URL),
                    }
                )
            )

        if self.path == "/api/node":
            reindex_requested = NODE_REINDEX_FLAG_PATH.exists()
            reindex_required = _detect_reindex_required()
            try:
                s = _node_status()
                payload = dict(s)
                payload.update(
                    {
                        "cached": False,
                        "lastSeen": int(time.time()),
                        "reindexRequested": reindex_requested,
                        "reindexRequired": False,
                    }
                )
                return self._send(*_json(payload))
            except (HTTPError, URLError, RuntimeError) as e:
                cached = _read_node_cache()
                if cached:
                    payload = dict(cached["status"])
                    payload.update(
                        {
                            "cached": True,
                            "lastSeen": int(cached["t"]),
                            "error": str(e),
                            "reindexRequested": reindex_requested,
                            "reindexRequired": reindex_required,
                        }
                    )
                    return self._send(*_json(payload))
                return self._send(
                    *_json(
                        {
                            "error": str(e),
                            "reindexRequested": reindex_requested,
                            "reindexRequired": reindex_required,
                        },
                        status=503,
                    )
                )

        if self.path == "/api/pool":
            return self._send(*_json(_pool_api_cached()))

        if self.path == "/api/pool/workers":
            return self._send(*_json(_pool_workers_api_cached()))

        if self.path == "/api/blocks":
            return self._send(*_json(_blocks_api()))

        if self.path == "/api/luck":
            return self._send(*_json(_luck_api()))

        if self.path.startswith("/api/timeseries/pool"):
            try:
                query = ""
                if "?" in self.path:
                    _, query = self.path.split("?", 1)
                trail = "30m"
                for part in query.split("&"):
                    if part.startswith("trail="):
                        trail = part.split("=", 1)[1]
                        break
                pts = POOL_SERIES.query(trail=trail, max_points=1000)
                return self._send(*_json({"trail": trail, "points": pts}))
            except Exception as e:
                return self._send(*_json({"error": str(e)}, status=500))

        if self.path == "/api/widget/sync":
            return self._send(*_json(_widget_sync()))

        if self.path == "/api/widget/pool":
            return self._send(*_json(_widget_pool()))

        status, body, ct = _read_static(self.path if self.path != "/" else "/index.html")
        return self._send(status, body, ct)

    def do_POST(self):
        length = int(self.headers.get("content-length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b""
        if not raw:
            body = {}
        else:
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                # Some proxies/browsers may send a classic form submission instead of JSON.
                # Accept urlencoded bodies as a fallback (e.g. payoutAddress=...).
                try:
                    parsed = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
                    body = {k: (v[0] if len(v) == 1 else v) for k, v in parsed.items()}
                except Exception:
                    return self._send(*_json({"error": "invalid json"}, status=400))

        if self.path == "/api/settings":
            current = _current_settings()
            try:
                prune = int(body.get("prune", current.get("prune", 5500)))
            except Exception:
                return self._send(*_json({"error": "invalid prune"}, status=400))
            if prune != 0 and prune < 550:
                return self._send(*_json({"error": "prune must be 0 or >= 550 MiB"}, status=400))

            network = str(body.get("network", current.get("network", "mainnet")) or "mainnet").strip().lower()
            if network not in ("mainnet", "testnet4"):
                return self._send(*_json({"error": "network must be mainnet or testnet4"}, status=400))

            try:
                _update_prune_conf(prune)
                _update_network_conf(network)
            except Exception as e:
                return self._send(*_json({"error": str(e)}, status=400))

            return self._send(*_json({
                "ok": True,
                "settings": {"prune": prune, "network": network},
                "restartRequired": True,
                "networkChanged": network != current.get("network"),
            }))

        if self.path == "/api/pool/settings":
            payout_address = str(body.get("payoutAddress") or "")
            mindiff = body.get("mindiff")
            startdiff = body.get("startdiff")
            maxdiff = body.get("maxdiff")
            try:
                settings = _update_pool_settings_full(
                    payout_address=payout_address,
                    mindiff=mindiff,
                    startdiff=startdiff,
                    maxdiff=maxdiff,
                )
                return self._send(*_json({"ok": True, "settings": settings, "restartRequired": True}))
            except Exception as e:
                return self._send(*_json({"error": str(e)}, status=400))

        if self.path == "/api/pool/bestshare/reset":
            try:
                addrs: list[str] = []
                try:
                    conf = _read_ckpool_conf()
                    a = str(conf.get("btcaddress") or "").strip()
                    if a:
                        addrs.append(a)
                except Exception:
                    pass
                try:
                    addrs.extend(_payout_history_addresses())
                except Exception:
                    pass
                return self._send(*_json(_reset_ckpool_bestshare(addrs)))
            except Exception as e:
                return self._send(*_json({"error": str(e)}, status=500))

        if self.path == "/api/pool/workers/bestshare/reset":
            try:
                worker = str(body.get("worker") or body.get("workername") or body.get("name") or "").strip()
                return self._send(*_json(_reset_since_block_tracker_for_worker(worker)))
            except Exception as e:
                return self._send(*_json({"error": str(e)}, status=400))

        if self.path == "/api/blocks/backscan":
            enabled_raw = body.get("enabled", None)
            rescan = bool(body.get("rescan")) or bool(body.get("rebuild"))
            reset = bool(body.get("reset")) or bool(body.get("resetAndRescan"))
            from_month = body.get("fromMonth") or body.get("from_month") or body.get("from")
            speed = str(body.get("speed") or "").strip().lower()
            max_blocks_raw = body.get("maxBlocks") if body.get("maxBlocks") is not None else body.get("max_blocks")
            interval_raw = body.get("intervalS") if body.get("intervalS") is not None else body.get("interval_s")
            now_s = int(time.time())

            blocks_state = _read_json_file(BLOCKS_STATE_PATH)
            scan = blocks_state.get("backscan") if isinstance(blocks_state.get("backscan"), dict) else {}
            if reset:
                blocks_state["events"] = []
                scan = {}

            # Manual-only scan settings.
            max_blocks = None
            interval_s = None
            try:
                if max_blocks_raw is not None and str(max_blocks_raw).strip() != "":
                    max_blocks = int(float(max_blocks_raw))
            except Exception:
                max_blocks = None
            try:
                if interval_raw is not None and str(interval_raw).strip() != "":
                    interval_s = int(float(interval_raw))
            except Exception:
                interval_s = None

            if speed in ["slow", "normal", "fast", "unlimited"]:
                if speed == "slow":
                    max_blocks = 25
                    interval_s = 10
                elif speed == "fast":
                    max_blocks = 500
                    interval_s = 0
                elif speed == "unlimited":
                    max_blocks = 2000
                    interval_s = 0
                else:
                    max_blocks = 100
                    interval_s = 2

            if max_blocks is not None:
                scan["maxBlocks"] = max(1, min(BACKSCAN_MAX_BLOCKS_CAP, int(max_blocks)))
            if interval_s is not None:
                scan["intervalS"] = max(0, min(3600, int(interval_s)))

            from_ts = _parse_month_yyyy_mm(from_month)
            if from_ts is not None:
                scan["fromMonth"] = str(from_month)
                scan["fromTs"] = int(from_ts)

            # Enabling with no pointers is treated as a start request.
            if enabled_raw is True and not (scan.get("startHeight") is not None and scan.get("nextHeight") is not None):
                rescan = True

            if rescan or bool(body.get("resetAndRescan")):
                # Start (or restart) an on-chain history scan. It stays OFF by default unless the user enables it.
                try:
                    tip_h = int(_rpc_call("getblockcount"))
                except Exception:
                    tip_h = None

                start_h = None
                if tip_h is not None:
                    if scan.get("fromTs"):
                        start_h = _estimate_start_height(tip_h=tip_h, from_ts=int(scan["fromTs"]), spacing_s=600, buffer_blocks=10)
                    else:
                        install_t = _install_time_s()
                        approx_blocks = max(0, int((now_s - int(install_t)) / 600))
                        start_h = max(0, tip_h - approx_blocks - 10)

                # Keep existing events by default; just restart scan pointers (unless reset).
                for k in [
                    "startHeight",
                    "nextHeight",
                    "tipHeightAtStart",
                    "tipHeightLast",
                    "startedAt",
                    "updatedAt",
                    "lastRunAt",
                    "complete",
                    "completedAt",
                    "stale",
                ]:
                    scan.pop(k, None)

                if tip_h is not None and start_h is not None:
                    scan["startHeight"] = int(start_h)
                    scan["nextHeight"] = int(start_h)
                    scan["tipHeightAtStart"] = int(tip_h)
                scan["enabled"] = True if enabled_raw is None else bool(enabled_raw)
                scan["complete"] = False
                scan["stale"] = False
                scan["requestedAt"] = now_s
                scan["startedAt"] = now_s
                scan["updatedAt"] = now_s

            if enabled_raw is not None and not rescan:
                scan["enabled"] = bool(enabled_raw)
                scan["updatedAt"] = now_s

            blocks_state["backscan"] = scan
            _write_json_file(BLOCKS_STATE_PATH, blocks_state)
            return self._send(*_json({"ok": True, "backscan": scan}))

        if self.path == "/api/support/ticket":
            if not SUPPORT_TICKET_URL:
                return self._send(*_json({"error": "support not configured"}, status=503))

            subject = str(body.get("subject") or "").strip()
            message = str(body.get("message") or "").strip()
            email = str(body.get("email") or "").strip()

            if len(subject) < 3 or len(subject) > 120:
                return self._send(*_json({"error": "subject must be 3-120 chars"}, status=400))
            if len(message) < 10 or len(message) > 8000:
                return self._send(*_json({"error": "message must be 10-8000 chars"}, status=400))
            if email and len(email) > 200:
                return self._send(*_json({"error": "email too long"}, status=400))

            payload = _support_ticket_payload(subject=subject, message=message, email=email or None)
            try:
                bundle, filename = _build_support_bundle_zip(payload)
                status, resp = _post_support_bundle(
                    SUPPORT_TICKET_URL, bundle_bytes=bundle, filename=filename, timeout_s=20
                )
                if int(status) >= 400:
                    return self._send(*_json({"error": "support server error"}, status=502))
                try:
                    data = json.loads(resp.decode("utf-8", errors="replace"))
                    ticket = data.get("ticket") if isinstance(data, dict) else None
                except Exception:
                    ticket = None
            except Exception:
                return self._send(*_json({"error": "support server unreachable"}, status=502))

            return self._send(*_json({"ok": True, "ticket": ticket}))

        return self._send(*_json({"error": "not found"}, status=404))


def main():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    CKPOOL_STATUS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    POOL_SERIES.load()
    _ensure_trackers_initialized()
    _pool_cache_load()
    _pool_workers_cache_load()

    global INSTALL_ID
    INSTALL_ID = _get_or_create_install_id()

    stop_event = threading.Event()
    t = threading.Thread(target=_series_sampler, args=(stop_event,), daemon=True)
    t.start()

    t_pool = threading.Thread(target=_pool_cache_worker, args=(stop_event,), daemon=True)
    t_pool.start()

    t_pool_workers = threading.Thread(target=_pool_workers_cache_worker, args=(stop_event,), daemon=True)
    t_pool_workers.start()

    t_backscan = threading.Thread(target=_backscan_worker, args=(stop_event,), daemon=True)
    t_backscan.start()

    t2 = threading.Thread(target=_support_checkin_loop, args=(stop_event,), daemon=True)
    t2.start()

    ThreadingHTTPServer(("0.0.0.0", 3000), Handler).serve_forever()


if __name__ == "__main__":
    main()
