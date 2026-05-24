from pathlib import Path
from time import sleep
import time

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

pd.set_option("display.max_columns", None)

URL_MAIN = "https://www.flashscore.com"
TOURNAMENT_LIST_FILE = "data/tournament_lists/atp_tournaments.csv"

# Use either ALLOWED_YEARS or YEAR_START/YEAR_END.
YEAR_START = 2023
YEAR_END = 2023
ALLOWED_YEARS = None

# Single-worker scraper is slow but safest.
SKIP_EXISTING_COMPLETE = True
GET_RETRIES = 3
RETRY_SLEEP_SECONDS = 10

firefox_options = Options()
firefox_options.add_argument("--headless")


def safe_get(browser, url, retries=GET_RETRIES, sleep_seconds=RETRY_SLEEP_SECONDS):
    """Load a URL with retry protection for intermittent DNS/network failures."""
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            browser.get(url)
            return True

        except WebDriverException as e:
            last_error = e
            print(f"GET failed attempt {attempt}/{retries}: {url}")
            print(f"{type(e).__name__}: {str(e)[:250]}")

            if attempt < retries:
                sleep(sleep_seconds * attempt)

    print(f"Giving up URL after {retries} attempts: {url}")
    return False


def get_text_or_empty(browser, by, value):
    elements = browser.find_elements(by, value)
    return elements[0].text if elements else ""


def load_tournament_df():
    if Path(TOURNAMENT_LIST_FILE).exists():
        df = pd.read_csv(TOURNAMENT_LIST_FILE)
    else:
        # Fallback for quick one-off testing.
        df = pd.DataFrame([{
            "year": YEAR_START,
            "tourney_slug": "indian-wells-2023",
            "match_count": None
        }])

    if ALLOWED_YEARS is not None:
        df = df[df["year"].isin(ALLOWED_YEARS)]
    else:
        df = df[(df["year"] >= YEAR_START) & (df["year"] <= YEAR_END)]

    df = df.sort_values(["year", "tourney_slug"]).reset_index(drop=True)

    return df


def output_is_complete(filename, expected_match_count):
    path = Path(filename)

    if not path.exists():
        return False

    if expected_match_count is None or pd.isna(expected_match_count):
        # If we do not know expected count, any existing non-empty file is considered complete.
        try:
            return len(pd.read_csv(path)) > 0
        except Exception:
            return False

    try:
        existing_rows = len(pd.read_csv(path))
    except Exception:
        return False

    return existing_rows >= int(expected_match_count)


def scrape_match(match_id, tourney, browser):
    match_flashscore_id = match_id.get_attribute("id")[4:]
    print("Opening match:", match_id.get_attribute("id"))

    match_page = f"{URL_MAIN}/match/{match_flashscore_id}/"

    if not safe_get(browser, match_page):
        return None

    sleep(1.5)

    stats_links = browser.find_elements(By.PARTIAL_LINK_TEXT, "STATS")

    if not stats_links:
        print("No stats link found")
        return None

    stats_url = stats_links[0].get_attribute("href")

    if not safe_get(browser, stats_url):
        return None

    sleep(2.5)

    stat_rows = browser.find_elements(By.XPATH, "//div[@data-testid='wcl-statistics']")
    print("Stat rows found:", len(stat_rows))

    if not stat_rows:
        return None

    row_data = {}

    for row in stat_rows:
        values = row.find_elements(By.XPATH, ".//div[@data-testid='wcl-statistics-value']")
        category = row.find_element(By.XPATH, ".//div[@data-testid='wcl-statistics-category']").text

        if len(values) >= 2:
            row_data[f"{category}_left"] = values[0].text
            row_data[f"{category}_right"] = values[1].text

    player_links = browser.find_elements(By.CLASS_NAME, "participant__participantLink")
    players = [p.get_attribute("href").split("/")[4].strip() for p in player_links]

    row_data["player_left"] = players[0] if len(players) > 0 else ""
    row_data["player_right"] = players[1] if len(players) > 1 else ""
    row_data["date"] = get_text_or_empty(browser, By.CLASS_NAME, "duelParticipant__startTime")
    row_data["match_result"] = get_text_or_empty(browser, By.CLASS_NAME, "duelParticipant__score")
    row_data["match_info"] = tourney

    odds_elements = browser.find_elements(By.CLASS_NAME, "oddsValue")
    odds = [o.text for o in odds_elements[:2]]

    row_data["odds_left"] = odds[0] if len(odds) > 0 else ""
    row_data["odds_right"] = odds[1] if len(odds) > 1 else ""

    return row_data


script_start = time.perf_counter()

tournament_df = load_tournament_df()
print("Tournaments to scrape:", len(tournament_df))

for _, tournament_row in tournament_df.iterrows():
    tourney = tournament_row["tourney_slug"]
    expected_match_count = tournament_row.get("match_count", None)

    tourney_start = time.perf_counter()

    tourney_results = f"{URL_MAIN}/tennis/atp-singles/{tourney}/results/"
    filename = f"data/raw/{tourney}.csv"

    if SKIP_EXISTING_COMPLETE and output_is_complete(filename, expected_match_count):
        print("Skipping existing complete CSV:", filename)
        continue

    browser_results = webdriver.Firefox(options=firefox_options)

    try:
        if not safe_get(browser_results, tourney_results):
            print("Tournament page failed after retries; skipping:", tourney)
            continue

        sleep(2.5)

        matches = browser_results.find_elements(By.CLASS_NAME, "event__match")

        print(filename)
        print("Matches found:", len(matches))

        matches_data = []

        browser_match = webdriver.Firefox(options=firefox_options)

        try:
            for match_id in matches:
                try:
                    match_data = scrape_match(match_id, tourney, browser_match)

                    if match_data is not None:
                        matches_data.append(match_data)

                except Exception as e:
                    print("Match failed:", match_id.get_attribute("id"), type(e).__name__, str(e)[:200])
                    continue

        finally:
            browser_match.close()

        print("Rows collected:", len(matches_data))

        if matches_data:
            df = pd.DataFrame(matches_data)
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(filename, index=False)
            print("CSV written:", filename)
        else:
            print("No match data collected; CSV not written.")

    finally:
        browser_results.close()

    tourney_elapsed = time.perf_counter() - tourney_start
    print(f"Tournament finished in {tourney_elapsed:.2f} seconds ({tourney_elapsed / 60:.2f} minutes)")

script_elapsed = time.perf_counter() - script_start
print(f"Total script time: {script_elapsed:.2f} seconds ({script_elapsed / 60:.2f} minutes)")
