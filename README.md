# JEE Cutoff Finder

Scrapes **Round 6** cutoff data (General / Gender Neutral) from [collegepravesh.com](https://www.collegepravesh.com) for all 23 IITs and the Top 10 NITs, then filters branches based on your rank.

- **IITs** use your JEE Advanced rank
- **NITs** use your JEE Mains rank (OS quota only)

---

## Installation

Requires Python 3.10+.

```bash
pip install cloudscraper beautifulsoup4 lxml requests
```

`cloudscraper` is the preferred HTTP client as it handles the site's bot protection. If it's not installed, the script falls back to `requests` automatically.

---

## Usage

### Both IITs and NITs (most common)

```bash
python cutoff_finder.py --advanced-rank 2000 --mains-rank 8000
```

### IITs only

```bash
python cutoff_finder.py --advanced-rank 2000 --iit-only
```

### NITs only

```bash
python cutoff_finder.py --mains-rank 8000 --nit-only
```

### Save results to CSV

```bash
python cutoff_finder.py --advanced-rank 2000 --mains-rank 8000 --save results.csv
```

### Change the gap tolerance

```bash
python cutoff_finder.py --advanced-rank 2000 --mains-rank 8000 --gap 1000
```

---

## All flags

| Flag | Required | Default | Description |
|---|---|---|---|
| `--advanced-rank` | Yes (for IITs) | — | Your JEE Advanced rank |
| `--mains-rank` | Yes (for NITs) | — | Your JEE Mains rank |
| `--gap` | No | `1500` | How far below the closing rank to still show a branch |
| `--save` | No | — | Path to save results as a CSV file |
| `--iit-only` | No | — | Skip NITs; only needs `--advanced-rank` |
| `--nit-only` | No | — | Skip IITs; only needs `--mains-rank` |

---

## How the filter works

The filter is **asymmetric** — it treats branches you qualify for differently from ones you just missed:

```
closing rank >= your rank   →   always shown        (you are ELIGIBLE)
closing rank <  your rank   →   shown only if
                                your_rank - closing <= gap   (just missed, within tolerance)
closing rank <  your rank
AND your_rank - closing > gap  →   hidden            (too far out of reach)
```

**Example** with `--mains-rank 5000 --gap 1500`:

| Branch | Closing Rank | Gap | Shown? | Reason |
|---|---|---|---|---|
| CSE | 8000 | −3000 | Yes | Eligible (closing > your rank) |
| ECE | 5500 | −500 | Yes | Eligible (closing > your rank) |
| Mech | 4800 | +200 | Yes | Just missed, within 1500 |
| Civil | 3400 | +1600 | No | Missed by 1600, exceeds gap |

The gap column in the output is always `your rank − closing rank`, so a **negative gap means you're comfortably eligible**, and a **positive gap means you fell short by that many ranks**.

---

## Colleges covered

### IITs (23) — JEE Advanced

IIT Bombay, IIT Delhi, IIT Madras, IIT Kanpur, IIT Kharagpur, IIT Roorkee, IIT Guwahati, IIT Hyderabad, IIT Gandhinagar, IIT Indore, IIT Jodhpur, IIT Patna, IIT Bhubaneswar, IIT Mandi, IIT Tirupati, IIT Jammu, IIT Dharwad, IIT Bhilai, IIT Goa, IIT Palakkad, IIT (BHU) Varanasi, IIT (ISM) Dhanbad, IIT Ropar

### Top 15 NITs — JEE Mains (OS quota)

NIT Trichy, NIT Warangal, NIT Surathkal, NIT Calicut, NIT Allahabad, NIT Rourkela, NIT Kurukshetra, NIT Silchar, NIT Jaipur, NIT Durgapur, NIT Nagpur, NIT Delhi, NIT Surat, NIT Jamshedpur, NIT Bhopal

---

## Output

Results are printed to the terminal grouped by college type, sorted by gap (eligible entries first):

```
============================================================
  Advanced rank: 2000 | Mains rank: 8000   |   Below-closing tolerance: 1500
  Total matches: 14
============================================================
  College                      Type  Quota  Branch                             Opening  Closing      Gap  Status

  IITs -- JEE Advanced  [your rank: 2,000]
  IIT Roorkee                  IIT   N/A    Mechanical Engineering                 820    2,310   -310   ELIGIBLE
  IIT Guwahati                 IIT   N/A    Civil Engineering                    1,100    2,050    -50   ELIGIBLE
  IIT Patna                    IIT   N/A    Computer Science and Engineering     1,800    1,650   +350   just missed
  ...

  NITs -- JEE Mains (OS Quota)  [your rank: 8,000]
  NIT Trichy                   NIT   OS     Mechanical Engineering               3,106    8,339   -339   ELIGIBLE
  NIT Warangal                 NIT   OS     Chemical Engineering                 6,200    9,100 -1,100   ELIGIBLE
  NIT Surathkal                NIT   OS     Civil Engineering                    5,000    7,200   +800   just missed
  ...
```

The CSV output (if `--save` is used) contains the same data with an added `Status` column.

---

## Data source & caveats

- Data is scraped live from [collegepravesh.com](https://www.collegepravesh.com) at the time you run the script. Cutoffs shown are from **2025 Round 6**.
- These are **last year's cutoffs** — actual 2026 cutoffs will differ. Use this as a directional guide, not a guarantee.
- A 1.5-second delay is added between requests to avoid hammering the server.
- If a college's page has fewer than 6 rounds available, the script uses the last available round and prints a warning.
