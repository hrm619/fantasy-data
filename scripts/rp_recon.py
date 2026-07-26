"""Phase 0 recon for the Reception Perception (`rp`) source — read-only, no DB writes.

Answers the questions RP_SOURCE_PLAN.md §2 leaves open, which cannot be answered from
outside the paywall:

  1. Are the wpDataTables tables **client-side** (every row already in the HTML, so a plain
     authenticated GET is the whole ingest) or **server-side** (rows arrive via
     `admin-ajax.php?action=get_wdtable`, so we need the AJAX route)?
  2. What `table_id` does each data page carry, and what are its column headers?
  3. Is a CSV/Excel export button exposed on these tables?
  4. What does the QB table actually measure? (A QB is not route-charted; its schema
     cannot be designed until a real table has been read.)

Auth is the pipeline's saved-session store — log in once, headed, before running this:

    ff-rankings login rp

Nothing here writes to the database or to `data-dev/rp-site/csv/`; it saves raw HTML plus a
`recon.json` report so the follow-up work can be designed offline against real bytes.

Usage:
    python scripts/rp_recon.py --out data-dev/rp-site/recon
    python scripts/rp_recon.py --out data-dev/rp-site/recon --only wr-full-history
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Politeness: a subscription read at human pace, not a crawl.
DELAY_SECONDS = 2.0

# The paywall's tell. Any page containing this was fetched without a valid session.
PAYWALL_MARKER = "You must be a subscriber"

# The sortable "Player Data" pages, from the site's public nav (probed 2026-07-25).
# RB and QB stop at 2024-25 — confirmed with the user 2026-07-25 as not-yet-published
# rather than a URL we failed to find, so 2025 RB/QB charting does not exist to ingest.
DATA_PAGES: dict[str, str] = {
    "wr-full-history": "https://receptionperception.com/nfl-data-full-history/",
    "wr-2025": "https://receptionperception.com/nfl-wr-sortable-data-2025-26/",
    "wr-2024": "https://receptionperception.com/nfl-wr-sortable-data-2024-25/",
    "wr-prospects-2026": "https://receptionperception.com/wr-prospect-sortable-data-2026/",
    "wr-prospects-2025": "https://receptionperception.com/college-sortable-data-2025/",
    "wr-prospects-2024": "https://receptionperception.com/college-sortable-data-2024/",
    "rb-2024": "https://receptionperception.com/nfl-rb-sortable-data-2024-25/",
    "rb-prospects-2026": "https://receptionperception.com/2026-nfl-draft-rb-prospect-data/",
    "qb-2024": "https://receptionperception.com/nfl-qb-sortable-data-2024-25/",
}

# One profile per position — enough to pin the prose/chart structure for Layer 1.
PROFILE_PAGES: dict[str, str] = {
    "profile-wr": "https://receptionperception.com/jordan-addison-2025-player-profile/",
    "profile-rb": "https://receptionperception.com/cam-skattebo-2025-player-profile/",
    "profile-qb": "https://receptionperception.com/drake-maye-2025-player-profile/",
}

# wpDataTables marks its tables with `data-wpdatatable_id` and/or `id="table_N"`.
_TABLE_ID_RE = re.compile(r'data-wpdatatable_id=["\'](\d+)["\']')
_TABLE_ELEM_ID_RE = re.compile(r'<table[^>]+id=["\']table_(\d+)["\']')
# Server-side tables ship a nonce per table and point at admin-ajax.
_AJAX_URL_RE = re.compile(r'["\']([^"\']*admin-ajax\.php[^"\']*)["\']')
_SERVER_SIDE_RE = re.compile(r'serverSide["\']?\s*[:=]\s*(true|false|1|0)', re.IGNORECASE)
_NONCE_RE = re.compile(r'wdtNonce[_a-zA-Z0-9]*["\']?\s*[:=]\s*["\']([a-f0-9]+)["\']')
# Export buttons render as DataTables button classes or plain labels.
_EXPORT_HINTS = ("buttons-csv", "buttons-excel", "dt-button", "wdt-export", "tableToolsButton")


class _TableScanner(HTMLParser):
    """Collect per-<table> header cells and body row counts using only the stdlib.

    pandas.read_html would need lxml/bs4, neither of which fantasy-data depends on, and a
    recon script is the wrong place to add a dependency.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[dict[str, Any]] = []
        self._depth = 0
        self._in_thead = False
        self._in_tbody = False
        self._in_th = False
        self._cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrd = {k: (v or "") for k, v in attrs}
        if tag == "table":
            self._depth += 1
            self.tables.append(
                {
                    "elem_id": attrd.get("id", ""),
                    "wpdatatable_id": attrd.get("data-wpdatatable_id", ""),
                    "classes": attrd.get("class", ""),
                    "headers": [],
                    "tbody_rows": 0,
                }
            )
        elif not self.tables:
            return
        elif tag == "thead":
            self._in_thead = True
        elif tag == "tbody":
            self._in_tbody = True
        elif tag == "th":
            self._in_th = True
            self._cell = []
        elif tag == "tr" and self._in_tbody:
            self.tables[-1]["tbody_rows"] += 1

    def handle_endtag(self, tag: str) -> None:
        if not self.tables:
            return
        if tag == "table":
            self._depth = max(0, self._depth - 1)
            self._in_thead = self._in_tbody = False
        elif tag == "thead":
            self._in_thead = False
        elif tag == "tbody":
            self._in_tbody = False
        elif tag == "th" and self._in_th:
            self._in_th = False
            text = " ".join("".join(self._cell).split())
            if text:
                self.tables[-1]["headers"].append(text)

    def handle_data(self, data: str) -> None:
        if self._in_th:
            self._cell.append(data)


@dataclass
class PageRecon:
    key: str
    url: str
    status: int
    bytes: int
    paywalled: bool
    html_path: str = ""
    wpdatatable_ids: list[str] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    ajax_urls: list[str] = field(default_factory=list)
    server_side: list[str] = field(default_factory=list)
    has_nonce: bool = False
    export_hints: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    word_count: int = 0
    error: str = ""


def _session() -> requests.Session:
    """Build a requests session carrying the saved `rp` browser cookies.

    Reuses `fantasy_pipeline.scraper.auth` rather than standing up a second session store —
    see RP_SOURCE_PLAN.md §5.1. WordPress serves these pages server-side, so cookies plus
    plain HTTP are enough; no browser needed for recon.
    """
    try:
        from fantasy_pipeline.scraper.auth import load_cookies
    except ImportError as exc:  # pragma: no cover - depends on the editable install
        raise SystemExit(f"Could not import the pipeline auth helper: {exc}") from exc

    cookies = load_cookies("rp", domain_contains="receptionperception.com")
    if not cookies:
        raise SystemExit(
            "The saved 'rp' session has no receptionperception.com cookies.\n"
            "Log in once (headed) with:  ff-rankings login rp"
        )

    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT})
    sess.cookies.update(cookies)
    return sess


def _strip_tags(html: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return " ".join(text.split())


def recon_page(sess: requests.Session, key: str, url: str, out_dir: Path) -> PageRecon:
    try:
        resp = sess.get(url, timeout=60)
    except requests.RequestException as exc:
        return PageRecon(key=key, url=url, status=0, bytes=0, paywalled=False, error=str(exc))

    html = resp.text
    paywalled = PAYWALL_MARKER.lower() in html.lower()

    html_path = out_dir / "html" / f"{key}.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")

    scanner = _TableScanner()
    try:
        scanner.feed(html)
    except Exception as exc:  # noqa: BLE001 - recon must never die on odd markup
        return PageRecon(
            key=key,
            url=url,
            status=resp.status_code,
            bytes=len(html),
            paywalled=paywalled,
            html_path=str(html_path),
            error=f"table scan failed: {exc}",
        )

    ids = sorted(set(_TABLE_ID_RE.findall(html)) | set(_TABLE_ELEM_ID_RE.findall(html)))
    tables = [t for t in scanner.tables if t["headers"] or t["wpdatatable_id"] or t["tbody_rows"]]

    return PageRecon(
        key=key,
        url=url,
        status=resp.status_code,
        bytes=len(html),
        paywalled=paywalled,
        html_path=str(html_path),
        wpdatatable_ids=ids,
        tables=tables,
        ajax_urls=sorted(set(_AJAX_URL_RE.findall(html)))[:5],
        server_side=sorted(set(_SERVER_SIDE_RE.findall(html))),
        has_nonce=bool(_NONCE_RE.search(html)),
        export_hints=[h for h in _EXPORT_HINTS if h in html],
        images=sorted(set(re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)))[:20],
        word_count=len(_strip_tags(html).split()),
    )


def _print_report(results: list[PageRecon]) -> None:
    print("\n" + "=" * 78)
    print("RP PHASE 0 RECON")
    print("=" * 78)

    for r in results:
        flag = "ERROR" if r.error else ("PAYWALLED" if r.paywalled else "ok")
        print(f"\n[{flag}] {r.key}  ({r.status}, {r.bytes:,} bytes, {r.word_count:,} words)")
        print(f"  {r.url}")
        if r.error:
            print(f"  error: {r.error}")
            continue
        if r.wpdatatable_ids:
            print(f"  wpDataTables ids: {', '.join(r.wpdatatable_ids)}")
        for t in r.tables:
            tid = t["wpdatatable_id"] or t["elem_id"] or "?"
            print(f"    table {tid}: {t['tbody_rows']} tbody rows, {len(t['headers'])} headers")
            if t["headers"]:
                print(f"      {t['headers']}")
        if r.server_side:
            print(f"  serverSide flags seen: {r.server_side}")
        if r.ajax_urls:
            print(f"  admin-ajax refs: {r.ajax_urls}")
        print(f"  wdtNonce present: {r.has_nonce}")
        if r.export_hints:
            print(f"  export button hints: {r.export_hints}")
        if r.key.startswith("profile-") and r.images:
            print(f"  images ({len(r.images)}): {r.images[:6]}")

    print("\n" + "-" * 78)
    print("VERDICT")
    print("-" * 78)

    ok = [r for r in results if not r.paywalled and not r.error]
    paywalled = [r.key for r in results if r.paywalled]
    if paywalled and not ok:
        print(f"  ⚠ ALL {len(paywalled)} page(s) gated — the session is missing or expired.")
        print("    Re-run:  ff-rankings login rp")
        return
    if paywalled:
        # Partial gating is an ENTITLEMENT difference, not a session failure: the same cookies
        # unlocked every other page in the same run. Observed 2026-07-25 for the WR full-history
        # and 2024 college pages. Do not send the reader to re-login over this.
        print(f"  ⚠ {len(paywalled)} page(s) gated while {len(ok)} unlocked on the SAME session:")
        print(f"    {paywalled}")
        print("    That is a subscription-tier gap, not an expired login — see RP_SOURCE_PLAN.md §11.")

    data_pages = [r for r in results if not r.key.startswith("profile-") and not r.error]
    with_rows = [r for r in data_pages if any(t["tbody_rows"] > 1 for t in r.tables)]
    if with_rows:
        print(f"  ✅ CLIENT-SIDE: {len(with_rows)}/{len(data_pages)} data pages ship rows in the HTML.")
        print("     An authenticated GET is the whole extraction — no AJAX, no browser.")
    else:
        print("  → SERVER-SIDE: no rows in the HTML; pull via admin-ajax.php?action=get_wdtable")
        print("     using the table ids and nonce above (see RP_SOURCE_PLAN.md §5.2).")

    exports = [r.key for r in data_pages if r.export_hints]
    print(f"  Export-button hints in static HTML: {exports or 'none'}")
    print("    ⚠ Unreliable — DataTables renders its Excel/CSV/Copy buttons in JS, so a page with")
    print("      no hint here can still have them. Confirmed 2026-07-25: every table has them.")
    print("\n  Raw HTML saved for offline design work. Report: recon.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 0 recon for the Reception Perception source.")
    ap.add_argument("--out", default="data-dev/rp-site/recon", help="Output directory for HTML + recon.json")
    ap.add_argument("--only", action="append", default=None, help="Fetch only these keys (repeatable)")
    ap.add_argument("--skip-profiles", action="store_true", help="Data pages only")
    ns = ap.parse_args()

    targets: dict[str, str] = dict(DATA_PAGES)
    if not ns.skip_profiles:
        targets.update(PROFILE_PAGES)
    if ns.only:
        unknown = [k for k in ns.only if k not in targets]
        if unknown:
            raise SystemExit(f"Unknown key(s) {unknown}. Known: {sorted(targets)}")
        targets = {k: targets[k] for k in ns.only}

    out_dir = Path(ns.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    sess = _session()
    results: list[PageRecon] = []
    for i, (key, url) in enumerate(targets.items()):
        print(f"  fetching {key} ...", flush=True)
        results.append(recon_page(sess, key, url, out_dir))
        if i < len(targets) - 1:
            time.sleep(DELAY_SECONDS + random.uniform(0, 0.5))

    (out_dir / "recon.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2),
        encoding="utf-8",
    )
    _print_report(results)
    return 1 if any(r.error or r.paywalled for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
