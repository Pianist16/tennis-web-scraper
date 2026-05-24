from time import sleep
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

URL_MAIN = "https://www.flashscore.com"

YEAR_START = 2000
YEAR_END = 2026

OUTPUT_FILE = "data/tournament_lists/atp_tournaments.csv"

firefox_options = Options()
firefox_options.add_argument("--headless")


def extract_base_slug(href):
    parts = href.rstrip("/").split("/")
    return parts[-1]


browser = webdriver.Firefox(options=firefox_options)

try:
    # Step 1: collect base tournament slugs
    start_url = f"{URL_MAIN}/tennis/atp-singles/"
    print("Opening ATP page:", start_url)

    browser.get(start_url)
    sleep(5)

    links = browser.find_elements(By.TAG_NAME, "a")

    base_slugs = set()

    for link in links:
        href = link.get_attribute("href")

        if not href:
            continue

        if "/tennis/atp-singles/" in href:
            slug = extract_base_slug(href)

            bad_slugs = {"atp-singles", "#", "#[legal-age]", ""}

            if slug in bad_slugs:
                continue

            if slug.startswith("#"):
                continue

            base_slugs.add(slug)

            if slug not in ["atp-singles", "#"]:
                base_slugs.add(slug)

    base_slugs = sorted(base_slugs)

    print("Base slugs found:", len(base_slugs))
    print(base_slugs[:30])

    # Step 2: test generated year slugs
    rows = []

    for base_slug in base_slugs:
        for year in range(YEAR_START, YEAR_END + 1):
            tourney_slug = f"{base_slug}-{year}"
            tourney_url = f"{URL_MAIN}/tennis/atp-singles/{tourney_slug}/results/"

            print("Testing:", tourney_slug)

            browser.get(tourney_url)
            sleep(2.5)

            matches = browser.find_elements(By.CLASS_NAME, "event__match")
            match_count = len(matches)

            if match_count > 0:
                print("FOUND:", tourney_slug, "matches:", match_count)

                rows.append({
                    "year": year,
                    "base_slug": base_slug,
                    "tourney_slug": tourney_slug,
                    "tourney_url": tourney_url,
                    "match_count": match_count
                })

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_FILE, index=False)

    print("Saved:", OUTPUT_FILE)
    print("Total tournaments found:", len(df))
    print(df.head(30))

finally:
    browser.close()