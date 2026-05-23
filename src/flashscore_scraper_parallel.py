from time import sleep
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

pd.set_option("display.max_columns", None)

firefox_options = Options()
firefox_options.add_argument("--headless")

URL_MAIN = "https://www.flashscore.com"
TOURNEY_LIST = ["indian-wells-2023"]

script_start = time.perf_counter()

def get_text_or_empty(browser, by, value):
    elements = browser.find_elements(by, value)
    return elements[0].text if elements else ""


def scrape_match(match_id, tourney, browser):
    match_flashscore_id = match_id.get_attribute("id")[4:]
    print("Opening match:", match_id.get_attribute("id"))

    match_page = f"{URL_MAIN}/match/{match_flashscore_id}/"
    browser.get(match_page)
    sleep(1.5)

    stats_links = browser.find_elements(By.PARTIAL_LINK_TEXT, "STATS")

    if not stats_links:
        print("No stats link found")
        return None

    stats_url = stats_links[0].get_attribute("href")
    browser.get(stats_url)
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


for tourney in TOURNEY_LIST:
    tourney_start = time.perf_counter()

    tourney_results = f"{URL_MAIN}/tennis/atp-singles/{tourney}/results/"
    filename = f"data/raw/{tourney}.csv"

    browser_results = webdriver.Firefox(options=firefox_options)

    try:
        browser_results.get(tourney_results)
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
            df.to_csv(filename, index=False)
            print("CSV written:", filename)
        else:
            print("No match data collected; CSV not written.")

    finally:
        browser_results.close()

    tourney_elapsed = time.perf_counter() - tourney_start
    print(f"Tournament finished in {tourney_elapsed:.2f} seconds ({tourney_elapsed/60:.2f} minutes)")

script_elapsed = time.perf_counter() - script_start
print(f"Total script time: {script_elapsed:.2f} seconds ({script_elapsed/60:.2f} minutes)")