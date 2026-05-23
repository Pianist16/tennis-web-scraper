# tennis-web-scraper

This repository contains a Python-based web scraper for collecting tennis match statistics from the Flashscore website and exporting the results into CSV files.

The project mainly uses:
- Selenium
- pandas

The scraper is designed to process one tournament at a time, while allowing easy extension to multiple tournaments and additional match statistics depending on project needs.

## Sample output

A sample scraped dataset for the Indian Wells 2023 tournament is available in the `archive/` folder:

```text
archive/indian-wells-2023.csv