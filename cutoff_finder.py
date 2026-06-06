#!/usr/bin/env python3
"""
JEE Cutoff Finder - CollegePravesh Scraper
==========================================
Scrapes Round 6 cutoffs (General / Gender Neutral) from collegepravesh.com
for all IITs and Top 10 NITs, then filters eligible branches.

  IITs  -> JEE Advanced ranks  (no HS/OS split)
  NITs  -> JEE Mains ranks     (OS quota only)

Filter logic (applied independently per rank type):
  * closing rank >= your rank  ->  always shown  (you are eligible)
  * closing rank <  your rank  ->  shown only if  your_rank - closing <= gap
                                   (just missed; within striking distance)

REQUIREMENTS:
    pip install requests cloudscraper beautifulsoup4 lxml

Usage:
    python cutoff_finder.py --advanced-rank 2000 --mains-rank 8000
    python cutoff_finder.py --advanced-rank 2000 --mains-rank 8000 --gap 1000
    python cutoff_finder.py --advanced-rank 2000 --mains-rank 8000 --save results.csv
    python cutoff_finder.py --advanced-rank 2000 --iit-only
    python cutoff_finder.py --mains-rank 8000  --nit-only
"""

import time
import argparse
import csv
import sys
from dataclasses import dataclass
from typing import Optional

# ── HTTP client (cloudscraper preferred; falls back to requests) ──────────────
try:
    import cloudscraper
    _scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    def fetch_html(url: str) -> Optional[str]:
        try:
            r = _scraper.get(url, timeout=25)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"  [ERROR] {url}: {e}", file=sys.stderr)
            return None
except ImportError:
    import requests
    _SESSION = requests.Session()
    _SESSION.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.collegepravesh.com/cutoff/",
    })
    def fetch_html(url: str) -> Optional[str]:
        try:
            r = _SESSION.get(url, timeout=25)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"  [ERROR] {url}: {e}", file=sys.stderr)
            return None

from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL      = "https://www.collegepravesh.com/cutoff/{slug}-cutoff-2025/"
REQUEST_DELAY = 1.5   # polite delay between pages (seconds)
ROUND_INDEX   = 5     # 0-based index for Round 6 within the section

# ── College lists ─────────────────────────────────────────────────────────────

IITS = [
    ("IIT Bombay",         "iit-bombay"),
    ("IIT Delhi",          "iit-delhi"),
    ("IIT Madras",         "iit-madras"),
    ("IIT Kanpur",         "iit-kanpur"),
    ("IIT Kharagpur",      "iit-kharagpur"),
    ("IIT Roorkee",        "iit-roorkee"),
    ("IIT Guwahati",       "iit-guwahati"),
    ("IIT Hyderabad",      "iit-hyderabad"),
    ("IIT Gandhinagar",    "iit-gandhinagar"),
    ("IIT Indore",         "iit-indore"),
    ("IIT Jodhpur",        "iit-jodhpur"),
    ("IIT Patna",          "iit-patna"),
    ("IIT Bhubaneswar",    "iit-bhubaneswar"),
    ("IIT Mandi",          "iit-mandi"),
    ("IIT Tirupati",       "iit-tirupati"),
    ("IIT Jammu",          "iit-jammu"),
    ("IIT Dharwad",        "iit-dharwad"),
    ("IIT Bhilai",         "iit-bhilai"),
    ("IIT Goa",            "iit-goa"),
    ("IIT Palakkad",       "iit-palakkad"),
    ("IIT (BHU) Varanasi", "iit-bhu-varanasi"),
    ("IIT (ISM) Dhanbad",  "iit-ism-dhanbad"),
    ("IIT Ropar",          "iit-ropar"),
]

# Top 15 NITs by NIRF ranking
NITS = [
    ("NIT Trichy",      "nit-trichy"),
    ("NIT Warangal",    "nit-warangal"),
    ("NIT Surathkal",   "nit-surathkal"),
    ("NIT Calicut",     "nit-calicut"),
    ("NIT Allahabad",   "nit-allahabad"),
    ("NIT Rourkela",    "nit-rourkela"),
    ("NIT Kurukshetra", "nit-kurukshetra"),
    ("NIT Silchar",     "nit-silchar"),
    ("NIT Jaipur",      "nit-jaipur"),
    ("NIT Durgapur",    "nit-durgapur"),
    ("NIT Nagpur",      "nit-nagpur"),
    ("NIT Delhi",       "nit-delhi"),
    ("NIT Surat",       "nit-surat"),
    ("NIT Jamshedpur",  "nit-jamshedpur"),
    ("NIT Bhopal",      "nit-bhopal"),
]

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class CutoffRow:
    college:      str
    college_type: str   # "IIT" or "NIT"
    quota:        str   # "OS" / "HS" / "N/A"
    branch:       str
    opening_rank: int
    closing_rank: int
    gap:          int   # your_rank - closing_rank
                        #   negative = eligible (closing >= rank)
                        #   positive = just missed (closing < rank, within gap)

# ── Parsing helpers ───────────────────────────────────────────────────────────

def parse_rank(value: str) -> Optional[int]:
    """Convert a rank cell string to int. Returns None for '--', empty, non-numeric."""
    v = value.strip().rstrip("P")   # strip Preparatory-rank suffix
    if not v or v == "--":
        return None
    try:
        return int(v.replace(",", ""))
    except ValueError:
        return None


def get_section_tables(html: str) -> list:
    """
    Find the 'General - Gender Neutral' section and return its tables in order.
    Falls back to all page tables if the section boundary can't be detected.
    """
    soup = BeautifulSoup(html, "lxml")

    target = None
    for tag in soup.find_all(["h1","h2","h3","h4","h5","p","strong","div"]):
        text = tag.get_text(" ", strip=True)
        if "General" in text and "Gender Neutral" in text:
            if tag.name in ("h2","h3","h4","h5","p","strong") or len(text) < 60:
                target = tag
                break

    tables = []
    if target:
        for sib in target.next_siblings:
            if not hasattr(sib, "name") or sib.name is None:
                continue
            if sib.name in ("h2","h3","h4","h5") and sib is not target:
                break
            if sib.name == "table":
                tables.append(sib)
            else:
                for tbl in sib.find_all("table"):
                    tables.append(tbl)

    if len(tables) < 6:
        tables = soup.find_all("table")   # fallback

    return tables


def parse_iit_table(table, college_name: str) -> list[CutoffRow]:
    """IIT table layout: Branch | Opening | Closing  (no quota column)."""
    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td","th"])]
        if len(cells) < 3:
            continue
        if cells[0] in ("Branch name",) or cells[1] in ("Opening", ""):
            continue
        if len(cells) == 1 or not cells[1]:
            continue
        branch  = cells[0]
        opening = parse_rank(cells[1])
        closing = parse_rank(cells[2])
        if opening is None or closing is None:
            continue
        rows.append(CutoffRow(
            college=college_name, college_type="IIT",
            quota="N/A", branch=branch,
            opening_rank=opening, closing_rank=closing, gap=0,
        ))
    return rows


def parse_nit_table(table, college_name: str, quota_filter: str = "OS") -> list[CutoffRow]:
    """NIT table layout: Quota | Branch | Opening | Closing."""
    rows = []
    last_quota = ""
    for tr in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td","th"])]
        if len(cells) < 4:
            continue
        if cells[1] in ("Branch name", "Opening"):
            continue
        quota = cells[0].strip() if cells[0].strip() else last_quota
        if cells[0].strip():
            last_quota = cells[0].strip()
        if quota != quota_filter:
            continue
        branch  = cells[1]
        if not branch:
            continue
        opening = parse_rank(cells[2])
        closing = parse_rank(cells[3])
        if opening is None or closing is None:
            continue
        rows.append(CutoffRow(
            college=college_name, college_type="NIT",
            quota=quota, branch=branch,
            opening_rank=opening, closing_rank=closing, gap=0,
        ))
    return rows


# ── Scrape one college ────────────────────────────────────────────────────────

def scrape_college(name: str, slug: str, college_type: str,
                   quota_filter: str = "OS") -> list[CutoffRow]:
    print(f"  Fetching {name:<30}", end=" ", flush=True)
    html = fetch_html(BASE_URL.format(slug=slug))
    if not html:
        print("-> FAILED")
        return []

    tables = get_section_tables(html)
    if not tables:
        print("-> No tables found")
        return []

    if len(tables) < 6:
        print(f"-> Only {len(tables)} rounds; using last available", end=" ")
        round_table = tables[-1]
    else:
        round_table = tables[ROUND_INDEX]

    rows = (parse_iit_table(round_table, name)
            if college_type == "IIT"
            else parse_nit_table(round_table, name, quota_filter))

    print(f"-> OK ({len(rows)} branches)")
    time.sleep(REQUEST_DELAY)
    return rows


# ── Filter ────────────────────────────────────────────────────────────────────

def filter_by_rank(rows: list[CutoffRow], your_rank: int, gap: int) -> list[CutoffRow]:
    """
    Asymmetric filter:
      * closing >= your_rank  ->  always include  (eligible)
      * closing <  your_rank  ->  include only if  your_rank - closing <= gap
    """
    matches = []
    for row in rows:
        diff = your_rank - row.closing_rank   # negative = eligible, positive = missed
        if diff <= 0 or diff <= gap:
            row.gap = diff
            matches.append(row)
    return matches


# ── Output ────────────────────────────────────────────────────────────────────

def print_results(results: list[CutoffRow],
                  advanced_rank: Optional[int],
                  mains_rank: Optional[int],
                  gap: int):
    if not results:
        print("\n  No branches found matching the criteria.")
        return

    # Sort: IITs first, then NITs; within each group eligible first (gap <= 0), then by gap asc
    results.sort(key=lambda r: (0 if r.college_type == "IIT" else 1, r.gap))

    W = 112
    rank_parts = []
    if advanced_rank:
        rank_parts.append(f"Advanced rank: {advanced_rank:,}")
    if mains_rank:
        rank_parts.append(f"Mains rank: {mains_rank:,}")

    print(f"\n{'='*W}")
    print(f"  {' | '.join(rank_parts)}   |   Below-closing tolerance: {gap:,}")
    print(f"  Total matches: {len(results)}")
    print(f"{'='*W}")
    print(f"  {'College':<28} {'Type':<5} {'Quota':<5} {'Branch':<48} {'Opening':>8} {'Closing':>8} {'Gap':>8}  Status")
    print(f"  {'-'*W}")

    current_type = None
    for r in results:
        if r.college_type != current_type:
            current_type = r.college_type
            rank_shown = advanced_rank if current_type == "IIT" else mains_rank
            label = ("  IITs -- JEE Advanced" if current_type == "IIT"
                     else "  NITs -- JEE Mains (OS Quota)")
            print(f"\n{label}  [your rank: {rank_shown:,}]")

        gap_str = f"{r.gap:+,}"
        status  = "ELIGIBLE" if r.gap <= 0 else "just missed"
        print(f"  {r.college:<28} {r.college_type:<5} {r.quota:<5} {r.branch:<48} "
              f"{r.opening_rank:>8,} {r.closing_rank:>8,} {gap_str:>8}  {status}")

    print(f"\n  {'-'*W}")
    print("  gap = your rank - closing rank")
    print("  ELIGIBLE    : closing rank >= your rank (you qualify based on last year's data)")
    print("  just missed : closing rank < your rank, but within your tolerance")
    print(f"{'='*W}\n")


def save_csv(results: list[CutoffRow], filepath: str,
             advanced_rank: Optional[int], mains_rank: Optional[int]):
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "College", "Type", "Quota", "Branch",
            "Opening Rank", "Closing Rank", "Gap (Your Rank - Closing)", "Status"
        ])
        for r in results:
            status = ("ELIGIBLE (closing >= rank)"
                      if r.gap <= 0 else "just missed (within tolerance)")
            writer.writerow([
                r.college, r.college_type, r.quota, r.branch,
                r.opening_rank, r.closing_rank, r.gap, status
            ])
    print(f"  Results saved -> {filepath}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scrape JEE 2025 Round-6 cutoffs and find eligible/near-miss branches.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--advanced-rank", type=int, default=None,
                        help="Your JEE Advanced rank (used for IITs)")
    parser.add_argument("--mains-rank",    type=int, default=None,
                        help="Your JEE Mains rank (used for NITs)")
    parser.add_argument("--gap",           type=int, default=1500,
                        help="How far below the closing rank to still show (default: 1500)")
    parser.add_argument("--save",          type=str, default=None,
                        help="Save results to CSV, e.g. --save results.csv")
    parser.add_argument("--iit-only",      action="store_true",
                        help="Only scrape IITs (requires --advanced-rank)")
    parser.add_argument("--nit-only",      action="store_true",
                        help="Only scrape NITs (requires --mains-rank)")
    args = parser.parse_args()

    # Validation
    if not args.iit_only and not args.nit_only:
        if args.advanced_rank is None or args.mains_rank is None:
            parser.error("Provide both --advanced-rank and --mains-rank, "
                         "or use --iit-only / --nit-only with the relevant rank.")
    if not args.nit_only and args.advanced_rank is None:
        parser.error("--advanced-rank is required when scraping IITs.")
    if not args.iit_only and args.mains_rank is None:
        parser.error("--mains-rank is required when scraping NITs.")

    gap = args.gap

    print(f"\n{'='*60}")
    print(f"  JEE Cutoff Finder 2025 -- collegepravesh.com")
    if args.advanced_rank:
        print(f"  JEE Advanced rank : {args.advanced_rank:,}")
    if args.mains_rank:
        print(f"  JEE Mains rank    : {args.mains_rank:,}")
    print(f"  Below-closing gap : {gap:,}")
    print(f"  Filter            : General / Gender Neutral / Round 6")
    print(f"{'='*60}\n")

    all_rows: list[CutoffRow] = []

    if not args.nit_only:
        print("-- IITs (JEE Advanced) " + "-"*38)
        for name, slug in IITS:
            rows = scrape_college(name, slug, "IIT")
            all_rows.extend(filter_by_rank(rows, args.advanced_rank, gap))

    if not args.iit_only:
        print("\n-- Top 15 NITs (JEE Mains, OS quota) " + "-"*22)
        for name, slug in NITS:
            rows = scrape_college(name, slug, "NIT", quota_filter="OS")
            all_rows.extend(filter_by_rank(rows, args.mains_rank, gap))

    print_results(all_rows, args.advanced_rank, args.mains_rank, gap)

    if args.save:
        save_csv(all_rows, args.save, args.advanced_rank, args.mains_rank)


if __name__ == "__main__":
    main()
