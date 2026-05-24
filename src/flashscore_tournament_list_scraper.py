from pathlib import Path
from time import sleep
import time

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

URL_MAIN = "https://www.flashscore.com"

YEAR_START = 2000
YEAR_END = 2026

OUTPUT_FILE = "data/tournament_lists/atp_tournaments.csv"
PROGRESS_FILE = "data/tournament_lists/atp_tournament_candidates_progress.csv"

GET_RETRIES = 3
RETRY_SLEEP_SECONDS = 10

firefox_options = Options()
firefox_options.add_argument("--headless")


def safe_get(browser, url, retries=GET_RETRIES, sleep_seconds=RETRY_SLEEP_SECONDS):
    """Load a URL with retry protection for intermittent DNS/network failures."""
    for attempt in range(1, retries + 1):
        try:
            browser.get(url)
            return True

        except WebDriverException as e:
            print(f"GET failed attempt {attempt}/{retries}: {url}")
            print(f"{type(e).__name__}: {str(e)[:250]}")

            if attempt < retries:
                sleep(sleep_seconds * attempt)

    print(f"Giving up URL after {retries} attempts: {url}")
    return False


def extract_base_slug(href):
    parts = href.rstrip("/").split("/")
    return parts[-1]


def load_progress():
    path = Path(PROGRESS_FILE)

    if path.exists():
        return pd.read_csv(path)

    return pd.DataFrame(columns=[
        "year",
        "base_slug",
        "tourney_slug",
        "tourney_url",
        "tested",
        "valid",
        "match_count",
        "status"
    ])


def save_progress(progress_df):
    Path(PROGRESS_FILE).parent.mkdir(parents=True, exist_ok=True)
    progress_df.to_csv(PROGRESS_FILE, index=False)

    valid_df = progress_df[progress_df["valid"] == True].copy()

    if not valid_df.empty:
        valid_df = valid_df[["year", "base_slug", "tourney_slug", "tourney_url", "match_count"]]
        valid_df = valid_df.sort_values(["year", "tourney_slug"]).drop_duplicates().reset_index(drop=True)

    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    valid_df.to_csv(OUTPUT_FILE, index=False)


def collect_base_slugs(browser):
    start_url = f"{URL_MAIN}/tennis/atp-singles/"
    print("Opening ATP page:", start_url)

    if not safe_get(browser, start_url):
        raise RuntimeError("Could not load ATP singles page")

    sleep(5)

    links = browser.find_elements(By.TAG_NAME, "a")
    base_slugs = set()

    for link in links:
        href = link.get_attribute("href")

        if not href:
            continue

        if "/tennis/atp-singles/" not in href:
            continue

        slug = extract_base_slug(href)

        bad_slugs = {"atp-singles", "#", "#[legal-age]", ""}

        if slug in bad_slugs:
            continue

        if slug.startswith("#"):
            continue

        base_slugs.add(slug)

    base_slugs = sorted(base_slugs)

    print("Base slugs found:", len(base_slugs))
    print(base_slugs[:30])

    return base_slugs


script_start = time.perf_counter()

browser = webdriver.Firefox(options=firefox_options)

try:
    base_slugs = collect_base_slugs(browser)

    progress_df = load_progress()
    tested_keys = set(zip(progress_df["base_slug"], progress_df["year"]))

    for base_slug in base_slugs:
        for year in range(YEAR_START, YEAR_END + 1):
            if (base_slug, year) in tested_keys:
                print("Skipping already tested:", f"{base_slug}-{year}")
                continue

            tourney_slug = f"{base_slug}-{year}"
            tourney_url = f"{URL_MAIN}/tennis/atp-singles/{tourney_slug}/results/"

            print("Testing:", tourney_slug)

            row = {
                "year": year,
                "base_slug": base_slug,
                "tourney_slug": tourney_slug,
                "tourney_url": tourney_url,
                "tested": True,
                "valid": False,
                "match_count": 0,
                "status": "not_found"
            }

            if safe_get(browser, tourney_url):
                sleep(2.5)

                matches = browser.find_elements(By.CLASS_NAME, "event__match")
                match_count = len(matches)

                if match_count > 0:
                    print("FOUND:", tourney_slug, "matches:", match_count)
                    row["valid"] = True
                    row["match_count"] = match_count
                    row["status"] = "found"
            else:
                row["status"] = "get_failed"

            progress_df = pd.concat([progress_df, pd.DataFrame([row])], ignore_index=True)
            tested_keys.add((base_slug, year))

            # Save after every candidate so progress survives network/router failure.
            save_progress(progress_df)

    print("Saved:", OUTPUT_FILE)
    print("Total tournaments found:", len(progress_df[progress_df["valid"] == True]))

finally:
    browser.close()

script_elapsed = time.perf_counter() - script_start
print(f"Total script time: {script_elapsed:.2f} seconds ({script_elapsed / 60:.2f} minutes)")
