from concurrent.futures import ThreadPoolExecutor, as_completed
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
TOURNAMENT_LIST_FILE = "data/tournament_lists/atp_tournaments_history.csv"

YEAR_START = 2020
YEAR_END = 2025
ALLOWED_YEARS = None

MIN_COMPLETION_RATE = 0.90

MAX_WORKERS = 4

SKIP_EXISTING_COMPLETE = True

GET_RETRIES = 3
RETRY_SLEEP_SECONDS = 10

PRECHECK_FIRST_N_MATCHES = 8

firefox_options = Options()
firefox_options.add_argument("--headless")


def safe_get(browser, url, retries=GET_RETRIES, sleep_seconds=RETRY_SLEEP_SECONDS):
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


def get_text_or_empty(browser, by, value):
    elements = browser.find_elements(by, value)
    return elements[0].text if elements else ""


def load_tournament_df():
    df = pd.read_csv(TOURNAMENT_LIST_FILE)

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

    try:
        existing_rows = len(pd.read_csv(path))
    except Exception:
        return False

    if expected_match_count is None or pd.isna(expected_match_count):
        return existing_rows > 0

    expected_match_count = int(expected_match_count)

    if expected_match_count == 0:
        return existing_rows > 0

    completion_rate = existing_rows / expected_match_count

    if completion_rate >= MIN_COMPLETION_RATE:
        print(
            f"Existing CSV is complete enough: {filename} "
            f"({existing_rows}/{expected_match_count}, {completion_rate:.1%})"
        )
        return True

    print(
        f"Existing CSV below completion threshold: {filename} "
        f"({existing_rows}/{expected_match_count}, {completion_rate:.1%})"
    )
    return False


def extract_set_score(div_element):
    full_text = div_element.text.strip()

    if not full_text:
        return "", ""

    main_score = full_text.split("\n")[0].strip()

    tiebreak_elements = div_element.find_elements(By.TAG_NAME, "sup")

    tiebreak = ""
    if tiebreak_elements:
        tiebreak = tiebreak_elements[0].text.strip()

    return main_score, tiebreak


def extract_match_scores(browser):
    score_data = {
        "match_result_sets": "",
        "sets_played": 0,
        "best_of_estimate": "",
        "score_full": "",
    }

    for set_num in range(1, 6):
        score_data[f"set_{set_num}_score"] = ""
        score_data[f"set_{set_num}_tiebreak"] = ""

    home_sets = get_text_or_empty(
        browser,
        By.CSS_SELECTOR,
        ".smh__score.smh__home"
    )

    away_sets = get_text_or_empty(
        browser,
        By.CSS_SELECTOR,
        ".smh__score.smh__away"
    )

    score_data["match_result_sets"] = f"{home_sets}-{away_sets}"

    set_strings = []

    sets_played = 0

    for set_num in range(1, 6):
        home_selector = f".smh__home.smh__part--{set_num}"
        away_selector = f".smh__away.smh__part--{set_num}"

        home_elements = browser.find_elements(By.CSS_SELECTOR, home_selector)
        away_elements = browser.find_elements(By.CSS_SELECTOR, away_selector)

        if not home_elements or not away_elements:
            continue

        home_score, home_tb = extract_set_score(home_elements[0])
        away_score, away_tb = extract_set_score(away_elements[0])

        if not home_score and not away_score:
            continue

        sets_played += 1

        set_score = f"{home_score}-{away_score}"

        tiebreak = ""
        if home_tb and away_tb:
            tiebreak = f"{home_tb}-{away_tb}"

        score_data[f"set_{set_num}_score"] = set_score
        score_data[f"set_{set_num}_tiebreak"] = tiebreak

        if tiebreak:
            set_strings.append(f"{set_score}({tiebreak})")
        else:
            set_strings.append(set_score)

    score_data["sets_played"] = sets_played

    try:
        max_sets = max(int(home_sets), int(away_sets))

        if max_sets >= 3:
            score_data["best_of_estimate"] = 5
        else:
            score_data["best_of_estimate"] = 3

    except Exception:
        score_data["best_of_estimate"] = ""

    score_data["score_full"] = (
        f"{score_data['match_result_sets']} | "
        + " | ".join(set_strings)
    )

    return score_data


def scrape_match_worker(match_index, match_flashscore_id, tourney):
    browser = webdriver.Firefox(options=firefox_options)

    try:
        print(f"Opening match {match_index}: {match_flashscore_id}")

        match_page = f"{URL_MAIN}/match/{match_flashscore_id}/"

        sleep((match_index % MAX_WORKERS) * 0.3)

        if not safe_get(browser, match_page):
            return {
                "status": "failed",
                "data": None
            }

        sleep(1.5)

        score_data = extract_match_scores(browser)

        stats_links = browser.find_elements(By.PARTIAL_LINK_TEXT, "STATS")

        if not stats_links:
            print(f"No stats link found for match {match_index}: {match_flashscore_id}")

            return {
                "status": "no_stats",
                "data": None
            }

        stats_url = stats_links[0].get_attribute("href")

        if not safe_get(browser, stats_url):
            return {
                "status": "failed",
                "data": None
            }

        sleep(2.5)

        stat_rows = browser.find_elements(
            By.XPATH,
            "//div[@data-testid='wcl-statistics']"
        )

        print(f"Match {match_index}: stat rows found: {len(stat_rows)}")

        if not stat_rows:
            return {
                "status": "no_stats",
                "data": None
            }

        row_data = {"match_index": match_index}

        for row in stat_rows:
            values = row.find_elements(
                By.XPATH,
                ".//div[@data-testid='wcl-statistics-value']"
            )

            category = row.find_element(
                By.XPATH,
                ".//div[@data-testid='wcl-statistics-category']"
            ).text

            if len(values) >= 2:
                row_data[f"{category}_left"] = values[0].text
                row_data[f"{category}_right"] = values[1].text

        player_links = browser.find_elements(
            By.CLASS_NAME,
            "participant__participantLink"
        )

        players = [
            p.get_attribute("href").split("/")[4].strip()
            for p in player_links
        ]

        row_data["player_left"] = players[0] if len(players) > 0 else ""
        row_data["player_right"] = players[1] if len(players) > 1 else ""

        row_data["date"] = get_text_or_empty(
            browser,
            By.CLASS_NAME,
            "duelParticipant__startTime"
        )

        row_data["match_info"] = tourney

        row_data.update(score_data)

        #odds_elements = browser.find_elements(By.CLASS_NAME, "oddsValue")
        #odds = [o.text for o in odds_elements[:2]]

        #row_data["odds_left"] = odds[0] if len(odds) > 0 else ""
        #row_data["odds_right"] = odds[1] if len(odds) > 1 else ""

        return {
            "status": "ok",
            "data": row_data
        }

    except Exception as e:
        print(
            f"Match failed {match_index}: {match_flashscore_id} | "
            f"{type(e).__name__}: {str(e)[:200]}"
        )

        return {
            "status": "failed",
            "data": None
        }

    finally:
        browser.close()


script_start = time.perf_counter()

tournament_df = load_tournament_df()
print("Tournaments to scrape:", len(tournament_df))

for _, tournament_row in tournament_df.iterrows():
    tourney = tournament_row["tourney_slug"]

    expected_match_count = tournament_row.get(
        "match_count",
        None
    )

    tourney_start = time.perf_counter()

    results_url = tournament_row.get(
        "results_url",
        None
    )

    if results_url is None or pd.isna(results_url):
        results_url = f"{URL_MAIN}/tennis/atp-singles/{tourney}/results/"

    filename = f"data/raw/{tourney}.csv"

    if (
        SKIP_EXISTING_COMPLETE
        and output_is_complete(filename, expected_match_count)
    ):
        print("Skipping existing complete CSV:", filename)
        continue

    browser_results = webdriver.Firefox(options=firefox_options)

    try:
        if not safe_get(browser_results, results_url):
            print("Tournament page failed after retries; skipping:", tourney)
            continue

        sleep(2.5)

        matches = browser_results.find_elements(
            By.CLASS_NAME,
            "event__match"
        )

        match_tasks = [
            (idx, match.get_attribute("id")[4:])
            for idx, match in enumerate(matches)
        ]

        print(filename)
        print("Results URL:", results_url)
        print("Matches found:", len(match_tasks))
        print("Expected matches:", expected_match_count)
        print("Max workers:", MAX_WORKERS)

    finally:
        browser_results.close()

    if not match_tasks:
        print("No matches found; skipping:", tourney)
        continue

    precheck_tasks = match_tasks[:PRECHECK_FIRST_N_MATCHES]

    matches_data = []
    precheck_statuses = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(scrape_match_worker, idx, match_id, tourney)
            for idx, match_id in precheck_tasks
        ]

        for future in as_completed(futures):
            result = future.result()

            precheck_statuses.append(result["status"])

            if result["status"] == "ok":
                matches_data.append(result["data"])

    print("Precheck statuses:", precheck_statuses)

    if (
        len(precheck_tasks) == PRECHECK_FIRST_N_MATCHES
        and precheck_statuses.count("no_stats") == PRECHECK_FIRST_N_MATCHES
    ):
        print(
            f"Skipping tournament {tourney}: "
            f"first {PRECHECK_FIRST_N_MATCHES} matches have no stats"
        )

        continue

    remaining_tasks = match_tasks[PRECHECK_FIRST_N_MATCHES:]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(scrape_match_worker, idx, match_id, tourney)
            for idx, match_id in remaining_tasks
        ]

        for future in as_completed(futures):
            result = future.result()

            if result["status"] == "ok":
                matches_data.append(result["data"])

    print("Rows collected:", len(matches_data))

    if matches_data:
        df = pd.DataFrame(matches_data)

        df = df.sort_values("match_index").reset_index(drop=True)

        df = df.drop(columns=["match_index"])

        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(filename, index=False)

        print("CSV written:", filename)

        if expected_match_count is not None and not pd.isna(expected_match_count):
            if len(df) < int(expected_match_count):
                print(
                    f"WARNING: incomplete scrape for {tourney}: "
                    f"{len(df)} rows collected vs "
                    f"{int(expected_match_count)} expected matches"
                )

    else:
        print("No match data collected; CSV not written.")

    tourney_elapsed = time.perf_counter() - tourney_start

    print(
        f"Tournament finished in {tourney_elapsed:.2f} seconds "
        f"({tourney_elapsed / 60:.2f} minutes)"
    )

script_elapsed = time.perf_counter() - script_start

print(
    f"Total script time: {script_elapsed:.2f} seconds "
    f"({script_elapsed / 60:.2f} minutes)"
)