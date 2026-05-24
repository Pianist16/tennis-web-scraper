from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep
import time

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

pd.set_option("display.max_columns", None)

URL_MAIN = "https://www.flashscore.com"
TOURNAMENT_LIST_FILE = "data/tournament_lists/atp_tournaments.csv"

YEAR_START = 2023
YEAR_END = 2023
ALLOWED_YEARS = None

def load_tournament_list():
    df = pd.read_csv(TOURNAMENT_LIST_FILE)

    if ALLOWED_YEARS is not None:
        df = df[df["year"].isin(ALLOWED_YEARS)]
    else:
        df = df[(df["year"] >= YEAR_START) & (df["year"] <= YEAR_END)]

    df = df.sort_values(["year", "tourney_slug"]).reset_index(drop=True)

    return df["tourney_slug"].tolist()

MAX_WORKERS = 4

firefox_options = Options()
firefox_options.add_argument("--headless")


def get_text_or_empty(browser, by, value):
    elements = browser.find_elements(by, value)
    return elements[0].text if elements else ""


def scrape_match_worker(match_index, match_flashscore_id, tourney):
    browser = webdriver.Firefox(options=firefox_options)

    try:
        print(f"Opening match {match_index}: {match_flashscore_id}")

        match_page = f"{URL_MAIN}/match/{match_flashscore_id}/"
        sleep((match_index % MAX_WORKERS) * 0.3)
        browser.get(match_page)
        sleep(1.5)

        stats_links = browser.find_elements(By.PARTIAL_LINK_TEXT, "STATS")

        if not stats_links:
            print(f"No stats link found for match {match_index}: {match_flashscore_id}")
            return None

        stats_url = stats_links[0].get_attribute("href")
        browser.get(stats_url)
        sleep(2.5)

        stat_rows = browser.find_elements(By.XPATH, "//div[@data-testid='wcl-statistics']")
        print(f"Match {match_index}: stat rows found: {len(stat_rows)}")

        if not stat_rows:
            return None

        row_data = {"match_index": match_index}

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

    except Exception as e:
        print(f"Match failed {match_index}: {match_flashscore_id} | {type(e).__name__}: {str(e)[:200]}")
        return None

    finally:
        browser.close()


script_start = time.perf_counter()


TOURNEY_LIST = load_tournament_list()
print("Tournaments to scrape:", len(TOURNEY_LIST))

for tourney in TOURNEY_LIST:
    tourney_start = time.perf_counter()

    tourney_results = f"{URL_MAIN}/tennis/atp-singles/{tourney}/results/"
    filename = f"data/raw/{tourney}.csv"

    browser_results = webdriver.Firefox(options=firefox_options)

    try:
        browser_results.get(tourney_results)
        sleep(2.5)

        matches = browser_results.find_elements(By.CLASS_NAME, "event__match")

        match_tasks = [
            (idx, match.get_attribute("id")[4:])
            for idx, match in enumerate(matches)
        ]

        print(filename)
        print("Matches found:", len(match_tasks))
        print("Max workers:", MAX_WORKERS)

    finally:
        browser_results.close()

    matches_data = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(scrape_match_worker, idx, match_id, tourney)
            for idx, match_id in match_tasks
        ]

        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                matches_data.append(result)

    print("Rows collected:", len(matches_data))

    if matches_data:
        df = pd.DataFrame(matches_data)
        df = df.sort_values("match_index").reset_index(drop=True)
        df = df.drop(columns=["match_index"])

        df.to_csv(filename, index=False)
        print("CSV written:", filename)
    else:
        print("No match data collected; CSV not written.")

    tourney_elapsed = time.perf_counter() - tourney_start
    print(f"Tournament finished in {tourney_elapsed:.2f} seconds ({tourney_elapsed / 60:.2f} minutes)")

script_elapsed = time.perf_counter() - script_start
print(f"Total script time: {script_elapsed:.2f} seconds ({script_elapsed / 60:.2f} minutes)")