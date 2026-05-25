from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import sleep
import math
import re
import time

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

URL_MAIN = "https://www.flashscore.com"
OUTPUT_FILE = "data/tournament_lists/atp_tournaments_history.csv"

MAX_WORKERS = 1

GET_RETRIES = 3
RETRY_SLEEP_SECONDS = 10

firefox_options = Options()
firefox_options.add_argument("--headless")


def safe_get(browser, url, retries=GET_RETRIES, sleep_seconds=RETRY_SLEEP_SECONDS):
    for attempt in range(1, retries + 1):
        try:
            browser.get(url)
            return True
        except WebDriverException as e:
            print(f"GET failed {attempt}/{retries}: {url}")
            print(f"{type(e).__name__}: {str(e)[:250]}")

            if attempt < retries:
                sleep(sleep_seconds * attempt)

    print(f"Giving up URL after {retries} attempts: {url}")
    return False


def chunk_list(items, number_of_chunks):
    chunk_size = math.ceil(len(items) / number_of_chunks)
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def extract_slug_from_url(url):
    return url.rstrip("/").split("/")[-1]


def extract_year_from_text_or_slug(text, slug):
    text_match = re.search(r"\b(19|20)\d{2}\b", text or "")
    if text_match:
        return int(text_match.group(0))

    slug_match = re.search(r"-(19|20)\d{2}$", slug or "")
    if slug_match:
        return int(slug[-4:])

    return None


def close_overlays(browser):
    buttons = browser.find_elements(
        By.XPATH,
        "//button[contains(., 'Accept') or contains(., 'I agree') or contains(., 'Agree') or contains(., 'OK')]"
    )

    for button in buttons:
        try:
            button.click()
            sleep(1)
            return
        except Exception:
            continue

def collect_base_tournament_links():
    browser = webdriver.Firefox(options=firefox_options)

    try:
        start_url = f"{URL_MAIN}/tennis/atp-singles/"
        print("Opening ATP Singles page:", start_url)

        if not safe_get(browser, start_url):
            raise RuntimeError("Could not open ATP Singles page")

        sleep(5)
        close_overlays(browser)
        sleep(1)

        # Click the ATP - Singles dropdown/list header so the full tournament list appears.
        dropdown_candidates = browser.find_elements(
            By.XPATH,
            "//span[contains(@class, 'lmc__elementName') and contains(., 'ATP')]"
        )

        if dropdown_candidates:
            browser.execute_script("arguments[0].click();", dropdown_candidates[0])
            sleep(2)
        else:
            print("WARNING: ATP dropdown header not found; collecting currently visible links only.")

        rows = []
        seen = set()

        def collect_visible_links():
            links = browser.find_elements(By.CSS_SELECTOR, "a.lmc__templateHref")

            for link in links:
                href = link.get_attribute("href")
                name = link.text.strip()

                if not href:
                    continue

                if not name:
                    continue

                if "/tennis/atp-singles/" not in href:
                    continue

                if href.rstrip("/") == f"{URL_MAIN}/tennis/atp-singles":
                    continue

                if "#" in href:
                    continue

                slug = extract_slug_from_url(href)

                bad_slugs = {"atp-singles", "#", "#[legal-age]", ""}

                if slug in bad_slugs or slug.startswith("#"):
                    continue

                if slug in seen:
                    continue

                seen.add(slug)

                rows.append({
                    "base_tourney_name": name,
                    "base_slug": slug,
                    "base_url": href.rstrip("/") + "/",
                    "archive_url": f"{URL_MAIN}/tennis/atp-singles/{slug}/archive/"
                })

        # Collect initially visible links.
        collect_visible_links()

        # Scroll the dropdown/list to reveal lazy-loaded tournament links.
        actions = ActionChains(browser)

        for _ in range(80):
            actions.send_keys(Keys.PAGE_DOWN).perform()
            sleep(0.25)
            collect_visible_links()

        df = pd.DataFrame(rows).sort_values("base_slug").reset_index(drop=True)

        print("Base tournaments found:", len(df))
        print(df.head(50))

        return df.to_dict("records")

    finally:
        browser.close()


def collect_archive_links_worker(worker_id, base_rows):
    browser = webdriver.Firefox(options=firefox_options)
    worker_rows = []

    try:
        for base_index, base_row in base_rows:
            base_slug = base_row["base_slug"]
            base_name = base_row["base_tourney_name"]
            archive_url = base_row["archive_url"]

            print(f"Worker {worker_id} opening archive {base_index}: {archive_url}")

            if not safe_get(browser, archive_url):
                print(f"Worker {worker_id}: archive failed: {base_slug}")
                continue

            sleep(3)

            links = browser.find_elements(By.TAG_NAME, "a")
            seen_tourney_slugs = set()

            for link in links:
                href = link.get_attribute("href")
                text = link.text.strip()

                if not href:
                    continue

                if "/tennis/atp-singles/" not in href:
                    continue

                if "/archive/" in href:
                    continue

                if "#" in href:
                    continue

                tourney_slug = extract_slug_from_url(href)

                if not tourney_slug:
                    continue

                # Important:
                # Flashscore current/latest tournament URL may be base_slug only:
                #   acapulco
                # Older historical URLs usually include year:
                #   acapulco-2025, acapulco-2024, etc.
                if tourney_slug != base_slug and not tourney_slug.startswith(base_slug + "-"):
                    continue

                if tourney_slug in seen_tourney_slugs:
                    continue

                seen_tourney_slugs.add(tourney_slug)

                year = extract_year_from_text_or_slug(text, tourney_slug)

                worker_rows.append({
                    "base_index": base_index,
                    "base_tourney_name": base_name,
                    "base_slug": base_slug,
                    "year": year,
                    "tourney_name": text,
                    "tourney_slug": tourney_slug,
                    "tourney_url": href.rstrip("/") + "/",
                    "results_url": href.rstrip("/") + "/results/",
                    "archive_url": archive_url
                })

            print(
                f"Worker {worker_id}: {base_slug} archive links found:",
                len(seen_tourney_slugs)
            )

        return worker_rows

    finally:
        browser.close()


script_start = time.perf_counter()

Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)

base_rows = collect_base_tournament_links()
indexed_base_rows = list(enumerate(base_rows))

chunks = chunk_list(indexed_base_rows, MAX_WORKERS)

all_rows = []

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [
        executor.submit(collect_archive_links_worker, worker_id, chunk)
        for worker_id, chunk in enumerate(chunks, start=1)
    ]

    for future in as_completed(futures):
        rows = future.result()
        all_rows.extend(rows)

        if all_rows:
            progress_df = pd.DataFrame(all_rows)
            progress_df = progress_df.drop_duplicates(subset=["tourney_slug"])
            progress_df = progress_df.sort_values(
                ["year", "tourney_slug"],
                na_position="last"
            ).reset_index(drop=True)
            progress_df.to_csv(OUTPUT_FILE, index=False)
            print("Progress saved:", OUTPUT_FILE, "rows:", len(progress_df))

df = pd.DataFrame(all_rows)

if not df.empty:
    df = df.drop_duplicates(subset=["tourney_slug"])
    df = df.sort_values(["year", "tourney_slug"], na_position="last").reset_index(drop=True)

df.to_csv(OUTPUT_FILE, index=False)

print("Saved:", OUTPUT_FILE)
print("Total historical tournaments found:", len(df))
print(df.head(50))

script_elapsed = time.perf_counter() - script_start
print(f"Total script time: {script_elapsed:.2f} seconds ({script_elapsed / 60:.2f} minutes)")