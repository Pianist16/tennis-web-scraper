from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep
import math
import time

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

URL_MAIN = "https://www.flashscore.com"

YEAR_START = 2000
YEAR_END = 2026

MAX_WORKERS = 4

OUTPUT_FILE = "data/tournament_lists/atp_tournaments.csv"

firefox_options = Options()
firefox_options.add_argument("--headless")


def extract_base_slug(href):
    parts = href.rstrip("/").split("/")
    return parts[-1]


def chunk_list(items, number_of_chunks):
    chunk_size = math.ceil(len(items) / number_of_chunks)

    return [
        items[i:i + chunk_size]
        for i in range(0, len(items), chunk_size)
    ]


def collect_base_slugs():
    browser = webdriver.Firefox(options=firefox_options)

    try:
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

    finally:
        browser.close()


def test_tournament_candidates(worker_id, candidate_tasks):
    browser = webdriver.Firefox(options=firefox_options)
    rows = []

    try:
        for task_index, base_slug, year in candidate_tasks:
            tourney_slug = f"{base_slug}-{year}"
            tourney_url = f"{URL_MAIN}/tennis/atp-singles/{tourney_slug}/results/"

            print(f"Worker {worker_id} testing {task_index}: {tourney_slug}")

            browser.get(tourney_url)
            sleep(2.5)

            matches = browser.find_elements(By.CLASS_NAME, "event__match")
            match_count = len(matches)

            if match_count > 0:
                print(f"FOUND by worker {worker_id}: {tourney_slug}, matches: {match_count}")

                rows.append({
                    "year": year,
                    "base_slug": base_slug,
                    "tourney_slug": tourney_slug,
                    "tourney_url": tourney_url,
                    "match_count": match_count
                })

        return rows

    except Exception as e:
        print(f"Worker {worker_id} failed: {type(e).__name__}: {str(e)[:300]}")
        return rows

    finally:
        browser.close()


script_start = time.perf_counter()

base_slugs = collect_base_slugs()

candidate_tasks = []

task_index = 0

for base_slug in base_slugs:
    for year in range(YEAR_START, YEAR_END + 1):
        candidate_tasks.append((task_index, base_slug, year))
        task_index += 1

print("Candidate tournament-year URLs:", len(candidate_tasks))
print("Max workers:", MAX_WORKERS)

chunks = chunk_list(candidate_tasks, MAX_WORKERS)

all_rows = []

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [
        executor.submit(test_tournament_candidates, worker_id, chunk)
        for worker_id, chunk in enumerate(chunks, start=1)
    ]

    for future in as_completed(futures):
        rows = future.result()
        all_rows.extend(rows)

df = pd.DataFrame(all_rows)

if not df.empty:
    df = df.sort_values(["year", "tourney_slug"]).reset_index(drop=True)

df.to_csv(OUTPUT_FILE, index=False)

print("Saved:", OUTPUT_FILE)
print("Total tournaments found:", len(df))
print(df.head(30))

script_elapsed = time.perf_counter() - script_start
print(f"Total script time: {script_elapsed:.2f} seconds ({script_elapsed / 60:.2f} minutes)")