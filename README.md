# tennis-web-scraper

Python-based web scraping pipeline for collecting professional ATP tennis match data and statistics from Flashscore.

The project uses:

- Python
- Selenium
- pandas
- Docker
- VS Code Dev Containers

---

## Features

The scraper currently supports:

- Tournament history scraping
- Match statistics scraping
- Match score extraction
- Set-by-set score parsing
- Tiebreak score parsing
- Parallel multi-worker scraping
- Structured CSV export

Collected statistics include:

- Aces
- Double faults
- First serve percentage
- Break points saved/converted
- Service points won
- Return points won
- Winners
- Unforced errors
- Net points won
- Match points saved
- And more

---

## Match Score Support

The scraper extracts:

```text
7-6(7-4) 6-4
6-3 3-6 7-6(10-8)
```

Supports:

- Best-of-3 matches
- Best-of-5 matches
- Tiebreak parsing

---

## Project Structure

```text
src/
    flashscore_tournament_history_scraper_parallel.py
    flashscore_scraper_parallel.py

data/raw/
    Scraped tournament CSV files

archive/
    Older scripts and experiments
```

---

## Development Environment

The project uses a containerized Docker + VS Code Dev Container workflow for reproducible development across systems.

Requirements:

- Docker
- VS Code
- Dev Containers extension

---

## Sample Output

Example datasets:

```text
data/raw/acapulco-2020.csv
data/raw/adelaide-2020.csv
```

Each dataset contains:

- Match statistics
- Player names
- Match scores
- Set scores
- Tiebreak information
- Tournament metadata

---

## Purpose

This repository serves as the data collection pipeline for downstream:

- Tennis analytics
- Elo modeling
- Machine learning
- Match prediction research

---

## Status

Active development.
