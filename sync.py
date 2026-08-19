#!/usr/bin/env python
"""Gimtel Reclamations - auto-fill Google Sheet from local Postgres.

Sheet layout:
  Row 1 : headers (switch_ref, cut_off_id, trans_date, orig_inst,
          orig_phone_number, receiv_inst_id, receiv_phone_number, montant,
          tx_type, status, decision). 'decision' is added if missing.
  You type lookup criteria into any of SEARCH_COLUMNS (switch_ref, or
  sender phone + amount/time, etc.) -- one transaction per row.
  The script fills the rest of that row from the database. 'decision'
  is left for you to fill in.

Runs forever (polls every POLL_INTERVAL_SECONDS). Launch it via the
Startup launcher so the only human action is typing into the sheet.
"""
import os
import time
import datetime
import email.utils
from decimal import Decimal
from string import ascii_uppercase

import gspread
import requests

import config


def col_letter(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = ascii_uppercase[r] + s
    return s


def fix_clock_skew():
    """Align JWT time with Google's server time when the local clock is off.

    Idempotent: safe to call on every script rerun (e.g. in Streamlit), because
    the offset is always computed relative to the real clock, not the patched one.
    """
    try:
        import google.auth._helpers as gh
        if getattr(gh, "_true_utcnow", None) is None:
            gh._true_utcnow = gh.utcnow
        resp = requests.head("https://www.google.com", timeout=10)
        date_hdr = resp.headers.get("Date")
        if not date_hdr:
            return
        server_dt = email.utils.parsedate_to_datetime(date_hdr)
        if server_dt.tzinfo is None:
            server_dt = server_dt.replace(tzinfo=datetime.timezone.utc)
        server_utc = server_dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        local_utc = datetime.datetime.utcnow()
        skew = (server_utc - local_utc).total_seconds()
        if abs(skew) < 1:
            gh.utcnow = gh._true_utcnow
            return
        gh.utcnow = lambda: gh._true_utcnow() + datetime.timedelta(seconds=skew)
        print(f"[info] system clock off by {skew:.0f}s; corrected for Google auth.")
    except Exception as exc:
        print(f"[warn] could not auto-correct clock skew: {exc}")


def db_connect():
    import psycopg2  # lazy import: not needed by the deployed Streamlit app
    if config.DB_TYPE == "postgresql":
        conn = psycopg2.connect(
            host=config.DB_HOST, port=config.DB_PORT,
            user=config.DB_USER, password=config.DB_PASSWORD,
            dbname=config.DB_NAME)
        conn.autocommit = True  # avoid holding transactions (lets DDL run)
        return conn
    elif config.DB_TYPE == "oracle":
        import oracledb
        conn = oracledb.connect(
            user=config.DB_USER, password=config.DB_PASSWORD,
            host=config.DB_HOST, port=config.DB_PORT,
            service_name=config.DB_NAME)
        conn.autocommit = True
        return conn
    raise ValueError(f"Unsupported DB_TYPE: {config.DB_TYPE}")


DB_COLUMNS = [c for c in config.RESULT_COLUMNS if c != "decision"]


def _same(a, b):
    """Compare a sheet value with a stored value, tolerating text/number forms."""
    if a is None or b is None:
        return a == b
    try:
        return float(a) == float(b)
    except (ValueError, TypeError):
        return str(a).strip() == str(b).strip()


def _norm_date(s):
    """Parse a typed date in ISO or French locale into 'YYYY-MM-DD' (or None)."""
    s = str(s).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, Decimal):
        return float(v)
    return v


def fetch_by_criteria(conn, criteria):
    """Return list of rows (each a list in DB_COLUMNS order) matching criteria."""
    conds, params = [], []
    if "switch_ref" in criteria:
        conds.append("switch_ref = %s"); params.append(criteria["switch_ref"])
    if "orig_phone_number" in criteria:
        conds.append("orig_phone_number = %s"); params.append(criteria["orig_phone_number"])
    if "montant" in criteria:
        raw = str(criteria["montant"]).strip().replace(" ", "")
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            raw = raw.replace(",", ".")
        conds.append("ABS(montant - %s) < 0.005"); params.append(float(raw))
    if "trans_date" in criteria:
        nd = _norm_date(criteria["trans_date"])
        if nd:
            conds.append("DATE(trans_date) = %s"); params.append(nd)
    if not conds:
        return []
    sql = (f"SELECT {', '.join(DB_COLUMNS)} FROM public.RECLAMATIONS "
           f"WHERE {' AND '.join(conds)} ORDER BY trans_date DESC")
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [[_fmt(v) for v in r] for r in cur.fetchall()]


def creds_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, config.GOOGLE_CREDS_FILE)


def open_sheet():
    gc = gspread.service_account(filename=creds_path())
    sh = gc.open_by_key(config.SHEET_ID)
    return sh.worksheet(config.SHEET_NAME) if config.SHEET_NAME else sh.sheet1


def open_workbook():
    gc = gspread.service_account(filename=creds_path())
    return gc.open_by_key(config.SHEET_ID)


_open_cache = {}  # name -> (object, timestamp)


def open_sheet_cached(ttl=60):
    """Open the target worksheet, reusing the handle for `ttl` seconds.

    Reusing the handle avoids a metadata `open_by_key` call on every access,
    which otherwise eats into the Google Sheets per-minute read quota. Retries
    on transient 429 quota errors instead of failing the whole operation.
    """
    cached = _open_cache.get("sheet")
    if cached and time.time() - cached[1] < ttl:
        return cached[0]
    for _ in range(4):
        try:
            ws = open_sheet()
            _open_cache["sheet"] = (ws, time.time())
            return ws
        except gspread.exceptions.APIError:
            time.sleep(8)
            _open_cache.pop("sheet", None)
    raise


def open_workbook_cached(ttl=60):
    cached = _open_cache.get("workbook")
    if cached and time.time() - cached[1] < ttl:
        return cached[0]
    for _ in range(4):
        try:
            wb = open_workbook()
            _open_cache["workbook"] = (wb, time.time())
            return wb
        except gspread.exceptions.APIError:
            time.sleep(8)
            _open_cache.pop("workbook", None)
    raise


def invalidate_open_cache():
    _open_cache.clear()


def users_worksheet():
    """Return the 'users' worksheet, creating it (with a header) if missing."""
    sh = open_workbook_cached()
    try:
        return sh.worksheet(config.USERS_SHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=config.USERS_SHEET, rows=100, cols=4)
        ws.update(values=[["username", "password", "role", "created_at"]],
                  range_name="A1", value_input_option="USER_ENTERED")
        return ws


def read_header_map(ws):
    row = ws.get(f"A{config.HEADER_ROW}:Z{config.HEADER_ROW}")[0]
    return {name: i + 1 for i, name in enumerate(row) if name}


def ensure_decision_header(ws, header_map):
    if "decision" in header_map:
        return header_map
    max_col = max(header_map.values()) if header_map else 0
    dec_col = max_col + 1
    ws.update(range_name=f"{col_letter(dec_col)}{config.HEADER_ROW}",
              values=[["decision"]], value_input_option="USER_ENTERED")
    header_map["decision"] = dec_col
    return header_map


def write_last_col(header_map):
    return max(header_map[c] for c in DB_COLUMNS)


def clear_row(ws, row, last):
    ws.batch_clear([f"A{row}:{col_letter(last)}{row}"])


def fill_row(ws, row, db_row, header_map, last):
    arr = [""] * last
    for i, colname in enumerate(DB_COLUMNS):
        cidx = header_map.get(colname)
        if cidx:
            arr[cidx - 1] = db_row[i]
    ws.update(range_name=f"A{row}:{col_letter(last)}{row}", values=[arr],
              value_input_option="USER_ENTERED")


def set_status_cell(ws, row, value, header_map):
    sidx = header_map.get("status")
    if not sidx:
        return
    ws.update(range_name=f"{col_letter(sidx)}{row}", values=[[value]],
              value_input_option="USER_ENTERED")


def _pid_alive(pid):
    """True if a Windows process with the given PID is still running."""
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x0400, False, pid)
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    except Exception:
        return False


def main():
    pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sync.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                old = int(f.read().strip())
            if _pid_alive(old):
                print(f"[info] sync.py already running as pid {old}; exiting.")
                return
        except (ValueError, OSError):
            pass
    try:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass
    fix_clock_skew()
    conn = db_connect()
    ws = open_sheet()
    header_map = read_header_map(ws)
    missing = [c for c in DB_COLUMNS if c not in header_map]
    if missing:
        raise SystemExit(
            f"Sheet missing required headers in row {config.HEADER_ROW}: {missing}")
    header_map = ensure_decision_header(ws, header_map)
    last = write_last_col(header_map)
    search_idx = {c: header_map[c] for c in config.SEARCH_COLUMNS if c in header_map}
    username_idx = header_map.get(config.USERNAME_COLUMN)

    last_filled = {}  # row -> dict of column values we last wrote / user typed
    print(f"Auto-fill started. Search columns: {list(search_idx)} "
          f"(poll every {config.POLL_INTERVAL_SECONDS}s). Ctrl+C to stop.")

    try:
        while True:
            try:
                # read the search columns for the whole data range at once
                rng = (f"{col_letter(min(search_idx.values()))}{config.FIRST_DATA_ROW}:"
                       f"{col_letter(max(search_idx.values()))}"
                       f"{config.FIRST_DATA_ROW + config.MAX_DATA_ROWS - 1}")
                block = ws.get(rng)
                user_col = (ws.col_values(username_idx)
                            if username_idx else [])
            except Exception as exc:
                print(f"[warn] cannot read sheet: {exc}")
            time.sleep(config.POLL_INTERVAL_SECONDS)

            for offset in range(config.MAX_DATA_ROWS):
                row = config.FIRST_DATA_ROW + offset
                has_user = bool(username_idx and row - 1 < len(user_col)
                               and (user_col[row - 1] or "").strip())
                # current values of search columns for this row
                cur = {}
                for col, cidx in search_idx.items():
                    rel = cidx - min(search_idx.values())  # 0-based within block
                    if offset < len(block) and rel < len(block[offset]):
                        v = (block[offset][rel] or "").strip()
                        if v:
                            cur[col] = v
                if not cur:
                    if row in last_filled:
                        clear_row(ws, row, last)
                        del last_filled[row]
                    continue
                if row in last_filled:
                    # only re-search the columns the user actually changed
                    effective = {c: v for c, v in cur.items()
                                 if c not in last_filled[row]
                                 or not _same(cur[c], last_filled[row][c])}
                    if not effective:
                        continue  # unchanged -> leave as is
                else:
                    effective = cur

                try:
                    matches = fetch_by_criteria(conn, effective)
                except Exception as exc:
                    print(f"[error] query failed for row {row} ({effective}): {exc}")
                    continue
                if matches:
                    fill_row(ws, row, matches[0], header_map, last)
                    last_filled[row] = {c: matches[0][i]
                                        for i, c in enumerate(DB_COLUMNS)}
                    if len(matches) > 1:
                        print(f"[info] row {row}: {len(matches)} matches, "
                              f"showing latest")
                else:
                    # No DB match. Manual rows (no user) are cleared + flagged;
                    # user-submitted rows are left intact (don't wipe their data).
                    if not has_user:
                        clear_row(ws, row, last)
                    set_status_cell(ws, row, "NOT FOUND", header_map)
                    last_filled[row] = dict(cur)
            time.sleep(config.POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        try:
            os.remove(pid_file)
        except OSError:
            pass
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
