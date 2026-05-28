# tennis-web-scraper

Python-based web scraping pipeline for collecting ATP tennis match statistics and metadata from Flashscore.com.

The repository focuses on:

* historical ATP match collection,
* structured statistical extraction,
* reproducible scraping workflows,
* large-scale dataset generation for downstream analytics and machine learning.

---

# Technology Stack

* Python
* Selenium
* pandas
* Docker
* VS Code Dev Containers

---

# Main Scripts

## Tournament History Scraper

```text
src/flashscore_tournament_history_scraper_parallel.py
```

Builds the historical tournament index from Flashscore archives.

Outputs:

```text
data/tournament_lists/atp_tournaments_history.csv
```

The generated file contains:

* tournament names,
* tournament slugs,
* yearly editions,
* results URLs,
* archive URLs,
* expected match counts.

This file acts as the primary input source for downstream match scraping.

---

## Automatic Match Scraper

```text
src/flashscore_scraper_parallel.py
```

Bulk scraper for historical tournament match statistics.

Main functionality:

* loads tournament history index,
* scrapes tournament result pages,
* extracts match-level statistics,
* extracts scorelines and tiebreaks,
* exports structured CSV datasets.

Supports:

* multi-worker parallel scraping,
* retry handling,
* automatic skipping of already-complete datasets,
* current/latest tournament routing logic.

Outputs:

```text
data/raw/<tournament-year>.csv
```

Example:

```text
data/raw/french-open-2025.csv
```

---

## Manual Tournament Scraper

```text
src/flashscore_scraper_manual_tournaments.py
```

Targeted scraper for ad hoc tournament scraping.

Useful for:

* incremental database updates,
* ongoing tournaments,
* rerunning failed tournaments,
* debugging,
* testing scraper changes.

Configured via:

```python
TOURNAMENT_SLUGS = [
    "french-open",
    "wimbledon",
]

YEARS = [
    2025,
]
```

---

# Project Structure

```text
src/
    flashscore_tournament_history_scraper_parallel.py
    flashscore_scraper_parallel.py
    flashscore_scraper_manual_tournaments.py

data/
    raw/
        Tournament CSV datasets

    tournament_lists/
        Tournament history index CSV

archive/
    Older scripts and experiments
```

---

# Extracted Data

The scraper extracts:

* player names,
* match dates,
* tournament metadata,
* match scores,
* set-by-set scores,
* tiebreak scores,
* bookmaker odds,
* match statistics.

Examples of extracted statistics:

* Aces
* Double Faults
* 1st Serve %
* Service Points Won
* Return Points Won
* Break Points Saved
* Break Points Converted
* Winners
* Unforced Errors
* Net Points Won

---

# Match Score Support

Examples:

```text
7-6(7-4) 6-4
6-3 3-6 7-6(10-8)
```

Supports:

* best-of-3 matches,
* best-of-5 matches,
* tiebreak parsing.

---

# Parallel Scraping Notes

Main worker configuration:

```python
MAX_WORKERS = 8
```

Recommended settings:

* stable mode: ~50% of total logical CPU cores,
* aggressive mode: ~75% of logical CPU cores.

Example:
* 16-core / 32-thread systems: typically stable around 8-12 workers.

Higher worker counts increase:

* Selenium/geckodriver instability,
* browser crashes,
* network failures,
* Flashscore throttling risk.

MAX_WORKERS is constrained more by Selenium/network stability than raw CPU compute.

---

# Networking Notes

VPNs, ad-blockers, DNS filters, and traffic-routing tools can interfere with Selenium networking.

Examples:

* WireGuard VPNs,
* Pi-hole,
* browser-level ad blockers,
* router-level DNS filtering.

Symptoms:

* geckodriver crashes,
* failed page loads,
* partial tournament scraping,
* empty match lists.

If instability appears:

* reduce `MAX_WORKERS`,
* temporarily disable VPN/ad-blocking,
* test direct outbound connectivity.

---

# Existing Dataset Handling

The scraper supports automatic skipping of already-complete datasets:

```python
SKIP_EXISTING_COMPLETE = True
```

This prevents unnecessary re-scraping of tournaments that already meet completion thresholds.

---

# Flashscore Routing Notes

Flashscore uses inconsistent routing for the latest/current tournament editions.

Examples:

```text
historical:
wimbledon-2024

latest/current:
wimbledon
```

The scraper includes logic for:

* historical year-specific tournament routing,
* latest-edition SUMMARY routing,
* automatic fallback handling.

This is particularly important for:

* ongoing seasons,
* recently completed tournaments,
* incremental database maintenance.

---

# Historical Data Coverage Notes

Match statistics availability varies significantly across years.

Observed behavior:

* 2012-2017:
  statistics often limited to later rounds
  (quarterfinals, semifinals, finals).

* 2018+:
  statistics become available for most ATP matches.

Because of this:

* earlier seasons are less statistically complete,
* modern seasons are significantly higher quality for ML applications.

---

# Development Environment

The repository uses a containerized Docker + VS Code Dev Container workflow for reproducible development across systems.

Requirements:

* Docker
* VS Code
* Dev Containers extension

---

# Purpose

This repository acts primarily as a data collection pipeline for:

* tennis analytics,
* Elo modeling,
* machine learning,
* match prediction research.

---

# Status

Active development.
