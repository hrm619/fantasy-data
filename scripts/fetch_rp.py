"""Fetch Reception Perception's sortable charting tables as CSV (Layer 0 capture).

Phase 1 of ../RP_SOURCE_PLAN.md. Drives the site's own wpDataTables CSV export button in an
authenticated browser and saves the result verbatim, plus a manifest. **Writes no database
rows** — parsing and loading happen offline, against these bytes, in a later phase.

Why the export button and not an API: the `admin-ajax.php?action=get_wdtable` endpoint returns
HTTP 200 with a zero-byte body for every request shape, cookies or not (probed 2026-07-25).
The export button works on every table and emits exactly the CSV layout the existing ingest
already parses — same header, and the `wdt_*` housekeeping columns stripped by the site's own
`columns: ':visible'` export option.

Auth: the pipeline's saved-session store. Log in once, headed:

    ff-rankings login rp

Usage:
    uv run --extra scrape python scripts/fetch_rp.py --page wr-2025
    uv run --extra scrape python scripts/fetch_rp.py --position WR
    uv run --extra scrape python scripts/fetch_rp.py --all --force
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Slug -> season lives in the package so it is unit-testable; the script only fetches.
from fantasy_data.ingest.rp_parse import season_from_slug

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Politeness between profile fetches: a subscription read at human pace, not a crawl.
DELAY_SECONDS = 2.0

# Layer 0 lives under the gitignored data-dev/ tree.
DEFAULT_OUT = "data-dev/rp-site"

PAYWALL_MARKER = "You must be a subscriber"

# Per-table sanity floor. A logged-out or truncated export must fail loudly rather than
# overwrite good data with a teaser — the same guard every pipeline fetcher uses.
DEFAULT_MIN_ROWS = 5


@dataclass(frozen=True)
class Page:
    """A sortable-data page and what its rows mean.

    `season` is the NFL season the page covers. For WR/RB it is belt-and-braces — those tables
    carry their own `Year` column, which the ingest should prefer. For **QB it is the only
    source of season**: tables 654/659/660 ship no Year column (../RP_SOURCE_PLAN.md §2.1), so a
    page-level value is the sole thing standing between us and a mislabelled season.
    """

    key: str
    url: str
    position: str
    season: int
    is_prospect: int = 0


# Probed from the site's public nav 2026-07-25. Two further pages exist but are gated above
# this subscription tier and are deliberately absent: /nfl-data-full-history/ (WR, all seasons)
# and /college-sortable-data-2024/. See ../RP_SOURCE_PLAN.md §11 — do not add them back without
# confirming the entitlement, or the fetcher will "succeed" with teaser pages.
PAGES: tuple[Page, ...] = (
    Page("wr-2025", "https://receptionperception.com/nfl-wr-sortable-data-2025-26/", "WR", 2025),
    Page("wr-2024", "https://receptionperception.com/nfl-wr-sortable-data-2024-25/", "WR", 2024),
    Page("wr-prospects-2026", "https://receptionperception.com/wr-prospect-sortable-data-2026/", "WR", 2025, 1),
    Page("wr-prospects-2025", "https://receptionperception.com/college-sortable-data-2025/", "WR", 2024, 1),
    Page("rb-2024", "https://receptionperception.com/nfl-rb-sortable-data-2024-25/", "RB", 2024),
    Page("rb-prospects-2026", "https://receptionperception.com/2026-nfl-draft-rb-prospect-data/", "RB", 2025, 1),
    Page("qb-2024", "https://receptionperception.com/nfl-qb-sortable-data-2024-25/", "QB", 2024),
)

PAGES_BY_KEY = {p.key: p for p in PAGES}


@dataclass
class TableCapture:
    page_key: str
    url: str
    position: str
    season: int
    is_prospect: int
    wdt_id: str
    dom_id: str
    tab_label: str
    csv_path: str = ""
    suggested_filename: str = ""
    rows: int = 0
    cols: int = 0
    header: list[str] = field(default_factory=list)
    info_line: str = ""
    sha256: str = ""
    error: str = ""


def _slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv_shape(path: Path) -> tuple[int, int, list[str]]:
    """Return (data_row_count, column_count, header) for a downloaded export."""
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return 0, 0, []
    return len(rows) - 1, len(rows[0]), rows[0]


def _button_labels(scope: Any) -> list[str]:
    return [t.strip() for t in scope.locator(".dt-button").all_inner_texts()]


def _export_table(page: Any, cap: TableCapture, out_dir: Path, min_rows: int) -> None:
    """Set the table to show everything, click its CSV button, and save the download."""
    dom_id = cap.dom_id

    # Server-side tables export only the rows currently loaded, so widen the page first.
    # Not every table has the selector (RB 653 has none — it is a single page of 15).
    sel = page.locator(f"select[name='{dom_id}_length']")
    if sel.count():
        options = [o.strip() for o in sel.locator("option").all_inner_texts()]
        if options:
            sel.select_option(label=options[-1])
            page.wait_for_timeout(4000)

    info = page.locator(f"#{dom_id}_info")
    if info.count():
        cap.info_line = info.inner_text().strip()

    wrapper = page.locator(f"#{dom_id}_wrapper")
    scope = wrapper if wrapper.count() else page
    labels = _button_labels(scope)
    lowered = [label.lower() for label in labels]
    if "csv" not in lowered:
        cap.error = f"no CSV export button (buttons seen: {labels})"
        return

    with page.expect_download(timeout=60000) as download_info:
        scope.locator(".dt-button").nth(lowered.index("csv")).click()
    download = download_info.value
    cap.suggested_filename = download.suggested_filename or ""

    # Name preference: the tab label (the seven WR/QB data types), else the site's own export
    # filename ("2024-25 NFL RB Data.csv"), else the bare table id. Untabbed pages have no
    # label, and `653.csv` tells a later reader nothing about what is in it.
    stem = Path(cap.suggested_filename).stem if cap.suggested_filename else ""
    name = f"{cap.page_key}__{_slug(cap.tab_label or stem or cap.wdt_id)}.csv"
    dest = out_dir / "csv" / cap.position / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    download.save_as(str(dest))

    cap.csv_path = str(dest)
    cap.rows, cap.cols, cap.header = _read_csv_shape(dest)
    cap.sha256 = _sha256(dest)

    if cap.rows < min_rows:
        cap.error = f"only {cap.rows} rows (floor {min_rows}) — truncated or logged-out export?"


def _tables_in_scope(page: Any) -> list[tuple[str, str]]:
    """Return (wdt_id, dom_id) for every currently-visible wpDataTable."""
    found: list[tuple[str, str]] = []
    tables = page.locator("table[data-wpdatatable_id]")
    for i in range(tables.count()):
        el = tables.nth(i)
        if not el.is_visible():
            continue
        wdt_id = el.get_attribute("data-wpdatatable_id") or ""
        dom_id = el.get_attribute("id") or ""
        if wdt_id and dom_id:
            found.append((wdt_id, dom_id))
    return found


def fetch_page(ctx: Any, spec: Page, out_dir: Path, min_rows: int) -> list[TableCapture]:
    """Export every table on one sortable-data page, walking its tabs if it has them."""
    page = ctx.new_page()
    caps: list[TableCapture] = []
    try:
        page.goto(spec.url, wait_until="networkidle", timeout=120000)

        if PAYWALL_MARKER.lower() in page.content().lower():
            return [
                TableCapture(
                    page_key=spec.key,
                    url=spec.url,
                    position=spec.position,
                    season=spec.season,
                    is_prospect=spec.is_prospect,
                    wdt_id="",
                    dom_id="",
                    tab_label="",
                    error="gated — subscriber teaser returned (tier gap or expired session)",
                )
            ]

        # The WR pages hold seven tables in jQuery-UI tabs; a table in an inactive tab has an
        # export button that exists but is not visible, and clicking it times out after 30s.
        # RB/QB pages are untabbed, so fall back to whatever is visible on load.
        tab_links = page.locator("ul.ui-tabs-nav a")
        tab_count = tab_links.count()
        seen: set[str] = set()

        for tab_index in range(max(tab_count, 1)):
            label = ""
            if tab_count:
                link = tab_links.nth(tab_index)
                label = link.inner_text().strip()
                link.click()
                page.wait_for_timeout(2500)

            for wdt_id, dom_id in _tables_in_scope(page):
                if wdt_id in seen:
                    continue
                seen.add(wdt_id)
                cap = TableCapture(
                    page_key=spec.key,
                    url=spec.url,
                    position=spec.position,
                    season=spec.season,
                    is_prospect=spec.is_prospect,
                    wdt_id=wdt_id,
                    dom_id=dom_id,
                    tab_label=label,
                )
                try:
                    _export_table(page, cap, out_dir, min_rows)
                except Exception as exc:  # keep going; one bad table shouldn't lose the page
                    cap.error = f"{type(exc).__name__}: {str(exc)[:200]}"
                caps.append(cap)
                status = cap.error or f"{cap.rows} rows x {cap.cols} cols"
                print(f"    [{wdt_id}] {label or '(untabbed)'}: {status}")
    finally:
        page.close()
    return caps


# ---------------------------------------------------------------------------
# Profiles (Layer 1 source material): prose + chart images, one post per player-season.
# ---------------------------------------------------------------------------

# Public index pages listing every profile post. Enumerable without a session; the profiles
# themselves are gated.
PROFILE_INDEXES: dict[str, str] = {
    "WR": "https://receptionperception.com/player-profiles-2/",
    "RB": "https://receptionperception.com/rb-player-profiles-page/",
    "QB": "https://receptionperception.com/qb-player-profiles-page/",
}

_PROFILE_HREF_RE = re.compile(r'href="https://receptionperception\.com/([a-z0-9\-]+-profile)/"')
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
_PUBLISHED_RE = re.compile(r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"')

# A real profile is 170KB+. The site intermittently answers 200 with a ~5KB stripped shell
# (observed once mid-run, recovering on its own) — status alone is not proof of content.
MIN_PROFILE_BYTES = 20_000


@dataclass
class ProfileCapture:
    slug: str
    url: str
    position: str
    season: int
    kind: str  # 'player' | 'prospect'
    title: str = ""
    published_at: str = ""
    html_path: str = ""
    bytes: int = 0
    sha256: str = ""
    error: str = ""


def discover_profiles(session: Any, positions: list[str]) -> list[ProfileCapture]:
    """Enumerate profile posts from the public index pages."""
    found: dict[str, ProfileCapture] = {}
    for position in positions:
        index_url = PROFILE_INDEXES[position]
        html = session.get(index_url, timeout=60).text
        slugs = sorted(set(_PROFILE_HREF_RE.findall(html)))
        skipped = 0
        for slug in slugs:
            parsed = season_from_slug(slug)
            if parsed is None:
                # Refuse to invent a season — an unlabelled entry is worse than a missing one.
                skipped += 1
                continue
            season, kind = parsed
            found.setdefault(
                slug,
                ProfileCapture(
                    slug=slug,
                    url=f"https://receptionperception.com/{slug}/",
                    position=position,
                    season=season,
                    kind=kind,
                ),
            )
        print(f"  {position}: {len(slugs)} profile links ({skipped} without a parseable season)")
    return list(found.values())


def _extract_meta(html: str) -> tuple[str, str]:
    """Return (title, published_at) from a profile page."""
    title = ""
    h1 = _H1_RE.search(html)
    if h1:
        title = " ".join(re.sub(r"<[^>]+>", " ", h1.group(1)).split())
    if not title:
        match = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
        if match:
            title = match.group(1).split("|")[0].strip()

    published_at = ""
    published = _PUBLISHED_RE.search(html)
    if published:
        published_at = published.group(1)[:10]
    return title, published_at


def fetch_profile(session: Any, cap: ProfileCapture, out_dir: Path, attempts: int = 3) -> None:
    """Fetch one profile page and save it, retrying a stripped or gated response."""
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            resp = session.get(cap.url, timeout=60)
        except Exception as exc:  # transport hiccup — worth one more try
            last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
            time.sleep(DELAY_SECONDS * attempt)
            continue

        html = resp.text
        if resp.status_code != 200:
            last_error = f"HTTP {resp.status_code}"
        elif PAYWALL_MARKER.lower() in html.lower():
            last_error = "gated — subscriber teaser (tier gap or expired session)"
        elif len(html) < MIN_PROFILE_BYTES:
            last_error = f"stripped response ({len(html)} bytes < {MIN_PROFILE_BYTES})"
        else:
            dest = out_dir / "html" / f"{cap.slug}.html"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(html, encoding="utf-8")
            cap.html_path = str(dest)
            cap.bytes = len(html)
            cap.sha256 = _sha256(dest)
            cap.title, cap.published_at = _extract_meta(html)
            return

        if attempt < attempts:
            time.sleep(DELAY_SECONDS * attempt)

    cap.error = last_error


def write_sources_yaml(caps: list[ProfileCapture], out_dir: Path) -> Path:
    """Emit a knowledge-base `files:` block for the captured profiles.

    Registered as local files rather than `articles:` so `kb` parses the HTML already on disk
    instead of re-fetching a paid site with a second copy of the session.
    """
    path = out_dir / "sources_rp.yaml"
    lines = [
        "# Generated by scripts/fetch_rp.py — paste under a domain's `files:` in",
        "# knowledge-base/config/sources.yaml.",
        "#",
        "# `season` is derived from the URL slug, NOT from published_at: RP publishes a season's",
        "# profiles the following summer, so season_for_date() would file every one a year late.",
        "# Prospect profiles use the season they charted (draft year - 1).",
        "files:",
    ]
    for cap in sorted(caps, key=lambda c: (c.position, -c.season, c.slug)):
        if cap.error or not cap.html_path:
            continue
        title = cap.title or cap.slug.replace("-", " ").title()
        # Absolute: `kb` resolves a relative `files:` path against its own config directory
        # (batch.py `config_dir / file_entry.path`), which is a different repo entirely.
        lines += [
            f"  - path: {json.dumps(str(Path(cap.html_path).resolve()))}",
            "    analyst: harmon",
            "    trust_tier: core",
            f"    title: {json.dumps(title)}",
            f"    published_at: {json.dumps(cap.published_at)}",
            f"    content_tag: {'prospect' if cap.kind == 'prospect' else 'profile'}",
            f"    season: {cap.season}",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_profiles(ns: argparse.Namespace, out_dir: Path, manifest: dict[str, Any]) -> list[ProfileCapture]:
    import requests

    from fantasy_pipeline.scraper.auth import load_cookies

    cookies = load_cookies("rp", domain_contains="receptionperception.com")
    if not cookies:
        raise SystemExit("No receptionperception.com cookies in the saved session. Run: ff-rankings login rp")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    session.cookies.update(cookies)

    positions = [p.upper() for p in (ns.position or PROFILE_INDEXES)]
    unknown = [p for p in positions if p not in PROFILE_INDEXES]
    if unknown:
        raise SystemExit(f"Unknown position(s) {unknown}. Known: {sorted(PROFILE_INDEXES)}")

    caps = discover_profiles(session, positions)
    if not ns.force:
        caps = [c for c in caps if f"profile:{c.slug}" not in manifest]
    if ns.limit:
        caps = caps[: ns.limit]
    print(f"  fetching {len(caps)} profile(s)")

    for i, cap in enumerate(caps, 1):
        fetch_profile(session, cap, out_dir)
        status = cap.error or f"{cap.bytes:,} bytes, season {cap.season}"
        print(f"    [{i}/{len(caps)}] {cap.slug}: {status}")
        if i < len(caps):
            time.sleep(DELAY_SECONDS + random.uniform(0, 0.5))
    return caps


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch Reception Perception sortable tables as CSV.")
    ap.add_argument("--out", default=DEFAULT_OUT, help=f"Layer 0 output root (default: {DEFAULT_OUT})")
    ap.add_argument("--page", action="append", help="Page key to fetch (repeatable)")
    ap.add_argument("--position", action="append", help="Fetch all pages for a position (WR/RB/QB)")
    ap.add_argument("--all", action="store_true", help="Fetch every known page")
    ap.add_argument("--force", action="store_true", help="Re-fetch pages already in the manifest")
    ap.add_argument("--min-rows", type=int, default=DEFAULT_MIN_ROWS, help="Per-table row floor")
    ap.add_argument("--headed", action="store_true", help="Run the browser headed (debugging)")
    ap.add_argument("--profiles", action="store_true", help="Capture profile prose/HTML instead of data tables")
    ap.add_argument("--limit", type=int, help="Profiles only: stop after N (for a smoke run)")
    ns = ap.parse_args()

    out_dir = Path(ns.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    if ns.profiles:
        # Profiles need no browser: the pages are server-rendered WordPress, so session cookies
        # plus plain HTTP are enough (mirrors fetch_fp_weekly_leaders in the pipeline).
        caps = run_profiles(ns, out_dir, manifest)
        for cap in caps:
            manifest[f"profile:{cap.slug}"] = asdict(cap)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        ok = [c for c in caps if not c.error]
        bad = [c for c in caps if c.error]
        yaml_path = write_sources_yaml(
            [ProfileCapture(**v) for k, v in manifest.items() if k.startswith("profile:")], out_dir
        )
        print(f"\n  captured {len(ok)} profile(s)")
        for c in bad:
            print(f"  ✗ {c.slug} — {c.error}")
        print(f"  manifest:    {manifest_path}")
        print(f"  kb sources:  {yaml_path}")
        return 1 if bad else 0

    selected: list[Page] = []
    if ns.all:
        selected = list(PAGES)
    else:
        for key in ns.page or []:
            if key not in PAGES_BY_KEY:
                raise SystemExit(f"Unknown page '{key}'. Known: {sorted(PAGES_BY_KEY)}")
            selected.append(PAGES_BY_KEY[key])
        for pos in ns.position or []:
            selected.extend(p for p in PAGES if p.position.upper() == pos.upper())
    if not selected:
        raise SystemExit("Nothing selected. Pass --all, --page <key>, or --position <WR|RB|QB>.")

    # Deduplicate while preserving order (--position WR --page wr-2025 shouldn't fetch twice).
    selected = list({p.key: p for p in selected}.values())

    if not ns.force:
        skipped = [p.key for p in selected if any(k.startswith(f"{p.key}:") for k in manifest)]
        if skipped:
            print(f"  already captured (use --force to refetch): {skipped}")
        selected = [p for p in selected if p.key not in skipped]
    if not selected:
        print("  nothing to do.")
        return 0

    from playwright.sync_api import sync_playwright

    from fantasy_pipeline.scraper.auth import load_storage_state, save_context_state

    storage_state = load_storage_state("rp")
    all_caps: list[TableCapture] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not ns.headed)
        try:
            ctx = browser.new_context(storage_state=storage_state, accept_downloads=True)
            for spec in selected:
                print(f"\n  {spec.key} ({spec.position} {spec.season}) {spec.url}")
                all_caps.extend(fetch_page(ctx, spec, out_dir, ns.min_rows))
            # Sliding session: capture any cookies the site rotated during the run.
            save_context_state(ctx, "rp")
        finally:
            browser.close()

    for cap in all_caps:
        manifest[f"{cap.page_key}:{cap.wdt_id or 'PAGE'}"] = asdict(cap)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    ok = [c for c in all_caps if not c.error]
    bad = [c for c in all_caps if c.error]
    print(f"\n  captured {len(ok)} table(s), {sum(c.rows for c in ok)} rows total")
    for c in bad:
        print(f"  ✗ {c.page_key}:{c.wdt_id or 'PAGE'} — {c.error}")
    print(f"  manifest: {manifest_path}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
