"""
Deletes generated book files from Supabase Storage a while after they were
made, so storage doesn't fill up.

- Every file in the generated-books bucket (print_ready.pdf, cover.pdf,
  digital_pages.pdf, in every regenerated version) is deleted
  CLEANUP_AFTER_DAYS days after it was uploaded (default 7).
- Orders whose saved links point at a deleted file get that link cleared,
  so the dashboard doesn't show a broken download button. The book can be
  regenerated from the order at any time.
- Customer photos (customer-photos bucket) are never touched: they're needed
  to regenerate a book.
- The digital book keeps working: Heyzine stores its own copy of the PDF
  when the flipbook is created.

Runs in the background of the book service: first 10 minutes after startup,
then every 12 hours. Set CLEANUP_AFTER_DAYS=0 on Render to switch it off.
"""

import os
import time
import threading
from datetime import datetime, timedelta, timezone

import requests

BUCKET = "generated-books"
URL_COLUMNS = ("print_pdf_url", "cover_pdf_url", "digital_pages_url")


def _headers(key):
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _list(base, key, prefix):
    """Every file under prefix (recursing into folders): [(path, created_at)]."""
    out, offset = [], 0
    while True:
        resp = requests.post(
            f"{base}/storage/v1/object/list/{BUCKET}",
            headers=_headers(key),
            json={"prefix": prefix, "limit": 1000, "offset": offset,
                  "sortBy": {"column": "name", "order": "asc"}},
            timeout=60,
        )
        resp.raise_for_status()
        items = resp.json()
        for it in items:
            path = f"{prefix}{it['name']}"
            if it.get("id") is None:          # a folder
                out += _list(base, key, path + "/")
            else:
                out.append((path, it.get("created_at")))
        if len(items) < 1000:
            return out
        offset += 1000


def _parse(ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def run_once(base, key, days, dry_run=False):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    old = [p for p, ts in _list(base, key, "") if _parse(ts) and _parse(ts) < cutoff]
    if not old:
        print(f"[cleanup] nothing older than {days} days")
        return []
    print(f"[cleanup] {len(old)} file(s) older than {days} days{' (dry run)' if dry_run else ''}")
    if dry_run:
        for p in old:
            print(f"[cleanup]   would delete {p}")
        return old

    for i in range(0, len(old), 500):
        batch = old[i:i + 500]
        resp = requests.delete(f"{base}/storage/v1/object/{BUCKET}",
                               headers=_headers(key), json={"prefixes": batch}, timeout=120)
        resp.raise_for_status()

    # clear order links that pointed at the deleted files
    cleared = 0
    for p in old:
        url = f"{base}/storage/v1/object/public/{BUCKET}/{p}"
        for col in URL_COLUMNS:
            resp = requests.patch(
                f"{base}/rest/v1/orders",
                headers={**_headers(key), "Prefer": "return=representation"},
                params={col: f"eq.{url}"},
                json={col: None},
                timeout=30,
            )
            if resp.ok:
                cleared += len(resp.json())
    print(f"[cleanup] deleted {len(old)} file(s), cleared {cleared} order link(s)")
    return old


def start_background(base, key):
    days = float(os.environ.get("CLEANUP_AFTER_DAYS", "7"))
    if days <= 0 or not base or not key:
        print("[cleanup] off")
        return

    def loop():
        time.sleep(600)
        while True:
            try:
                run_once(base, key, days)
            except Exception as e:  # never take the service down over cleanup
                print(f"[cleanup] failed: {e!r}")
            time.sleep(12 * 3600)

    threading.Thread(target=loop, daemon=True, name="storage-cleanup").start()
    print(f"[cleanup] on: generated books are deleted {days:g} days after they're made")
