#!/usr/bin/env python3
"""
United Airlines fare class availability scraper — batch JS extraction.
Clicks all details panels at once then extracts all fare data in a single JS call.

Usage:
    py scraper.py --origin ORD --destination LAX --date 2026-03-15
    py scraper.py --origin ORD --destination LAX --date 2026-03-15 --filter PZ
"""

import os
import re
import time
import json
import argparse
from datetime import datetime, timedelta
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

UNITED_HOME   = "https://www.united.com"
UPGRADE_CLASSES = {"PZ", "PN", "RN", "IN", "XN", "ZN"}
PROFILE_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile")


def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    env = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def parse_fare_classes(text):
    """Parse 'J9 C0 PZ4 ...' into {'J': 9, 'C': 0, 'PZ': 4, ...}"""
    return {m.group(1): int(m.group(2)) for m in re.finditer(r'([A-Z]{1,2})(\d)', text)}


def format_results(results, fare_filter=None):
    shown = 0
    for r in results:
        if fare_filter and not any(
            seg["classes"].get(fare_filter, 0) > 0 for seg in r["segments"]
        ):
            continue
        shown += 1
        print(f"\n{'-' * 52}")

        for seg in r["segments"]:
            print(f"  {seg['flight']}")
            if seg.get('depart') or seg.get('arrival'):
                print(f"  {seg['depart']} -> {seg['arrival']}")
            upgrade = {k: v for k, v in seg["classes"].items() if k in UPGRADE_CLASSES}
            regular = {k: v for k, v in seg["classes"].items() if k not in UPGRADE_CLASSES}

            if upgrade:
                print("  Upgrade classes:")
                for code, avail in upgrade.items():
                    mark = "+" if avail > 0 else "x"
                    print(f"    [{mark}] {code}: {avail}")

            if regular:
                print("  Fare classes:")
                chunks = [f"{code}{avail}" for code, avail in regular.items()]
                print("    " + "  ".join(chunks))

            if len(r["segments"]) > 1:
                print()

    return shown


def ensure_logged_in(driver, username=None, password=None):
    print("Checking login status...")
    driver.get(f"{UNITED_HOME}/en/us/united-mileageplus-signin/")

    if username and password:
        print("Login required, entering credentials automatically...")
        try:
            # Check if password field is already visible (username pre-filled)
            pwd_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            if not pwd_fields:
                # Step 1: fill username and click Continue
                user_field = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='text'], input[name*='user' i], input[id*='user' i]"))
                )
                user_field.click()
                user_field.send_keys(Keys.CONTROL + 'a')
                user_field.send_keys(username)
                continue_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH,
                        '//button[contains(translate(normalize-space(.),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"continue")]'
                    ))
                )
                driver.execute_script("arguments[0].click();", continue_btn)
            else:
                # Password field visible — check prefilled username matches via hidden input
                hidden = driver.find_elements(By.CSS_SELECTOR, "input[type='hidden'][id='username']")
                prefilled = hidden[0].get_attribute("value").strip() if hidden else ""
                if prefilled[-3:].lower() != username[-3:].lower():
                    # Wrong account — click Switch accounts and re-enter username
                    switch_btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "switch-account-button"))
                    )
                    driver.execute_script("arguments[0].click();", switch_btn)
                    user_field = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='text'], input[name*='user' i], input[id*='user' i]"))
                    )
                    user_field.click()
                    user_field.send_keys(Keys.CONTROL + 'a')
                    user_field.send_keys(username)
                    continue_btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH,
                            '//button[contains(translate(normalize-space(.),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"continue")]'
                        ))
                    )
                    driver.execute_script("arguments[0].click();", continue_btn)
            # Step 2: fill password
            pwd_field = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))
            )
            pwd_field.click()
            pwd_field.send_keys(password)
            pwd_field.send_keys(Keys.RETURN)
            WebDriverWait(driver, 30).until(
                lambda d: "sign" not in d.current_url
            )
            print("Login successful.")
            return
        except TimeoutException:
            print("Could not find login fields, falling back to manual login.")
    elif password:
        print("Login required, entering password automatically...")
        try:
            pwd_field = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))
            )
            pwd_field.click()
            pwd_field.send_keys(password)
            pwd_field.send_keys(Keys.RETURN)
            WebDriverWait(driver, 30).until(
                lambda d: "sign" not in d.current_url
            )
            print("Login successful.")
            return
        except TimeoutException:
            print("Could not find password field, falling back to manual login.")

    print("Please log in in the browser window.")
    print("The script will continue automatically once you are logged in.")

    WebDriverWait(driver, 300).until(
        lambda d: "sign" not in d.current_url
    )
    time.sleep(2)
    print("Login detected, continuing.")


MONTHS = ["January","February","March","April","May","June",
          "July","August","September","October","November","December"]

def pick_date(driver, wait, field_id, date_str):
    """Open the react-day-picker calendar and click the target date."""
    target = datetime.strptime(date_str, "%Y-%m-%d")

    for _ in range(3):
        wait.until(EC.element_to_be_clickable((By.ID, field_id))).click()
        try:
            WebDriverWait(driver, 5).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, ".rdp-caption_label")) > 0
            )
            break
        except TimeoutException:
            pass
    else:
        raise TimeoutException("Calendar did not open after 3 attempts")

    for _ in range(24):
        captions = driver.find_elements(By.CSS_SELECTOR, ".rdp-caption_label")
        displayed_months = []
        for cap in captions:
            text = cap.text.strip()
            for i, name in enumerate(MONTHS):
                if name in text:
                    try:
                        displayed_months.append(datetime(int(text.split()[-1]), i + 1, 1))
                    except ValueError:
                        pass
                    break

        if any(d.year == target.year and d.month == target.month for d in displayed_months):
            break

        if not displayed_months or displayed_months[0] < target.replace(day=1):
            btn = driver.find_element(By.CSS_SELECTOR,
                "button[name='next-month'], .rdp-nav_button_next, "
                "button[aria-label*='next' i], button[aria-label*='forward' i]"
            )
            driver.execute_script("arguments[0].click();", btn)
        else:
            btn = driver.find_element(By.CSS_SELECTOR,
                "button[name='previous-month'], .rdp-nav_button_previous, "
                "button[aria-label*='previous' i], button[aria-label*='backward' i]"
            )
            driver.execute_script("arguments[0].click();", btn)
        time.sleep(0.5)

    day_str = str(target.day)
    time.sleep(0.5)
    for _ in range(3):
        try:
            target_container = None
            for month_div in driver.find_elements(By.CSS_SELECTOR, ".rdp-month"):
                caption_els = month_div.find_elements(By.CSS_SELECTOR, ".rdp-caption_label")
                if not caption_els:
                    continue
                text = caption_els[0].text.strip()
                for i, name in enumerate(MONTHS):
                    if name in text:
                        try:
                            d = datetime(int(text.split()[-1]), i + 1, 1)
                            if d.month == target.month and d.year == target.year:
                                target_container = month_div
                        except ValueError:
                            pass
                        break

            search_root = target_container if target_container else driver
            day_buttons = search_root.find_elements(By.CSS_SELECTOR,
                ".rdp-day_button:not([disabled]), button.rdp-day:not([disabled])"
            )
            for btn in day_buttons:
                if btn.text.strip() == day_str:
                    driver.execute_script("arguments[0].click();", btn)
                    break
            break
        except Exception:
            time.sleep(0.5)
    time.sleep(0.5)


def get_search_url(origin, destination, date_str, return_date_str=None):
    if return_date_str:
        params = f"f={origin}&t={destination}&d={date_str}&r={return_date_str}&sc=7,7&px=1&taxng=1&newHP=True&clm=7&st=bestmatches&tqp=R"
    else:
        params = f"f={origin}&t={destination}&d={date_str}&tt=1&sc=7&px=1&taxng=1&newHP=True&clm=7&st=bestmatches&tqp=R"
    return f"{UNITED_HOME}/en/us/fsr/choose-flights?{params}"


def search(driver, origin, destination, date_str, return_date_str=None):
    trip_type = "round trip" if return_date_str else "one-way"
    print(f"Searching {origin} -> {destination} on {date_str} ({trip_type})...")
    driver.get(get_search_url(origin, destination, date_str, return_date_str))
    WebDriverWait(driver, 60).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, '[class*="flightHeaderRight"]')) > 0
    )
    time.sleep(2)
    print("Results loaded.")


def scrape_results(driver):
    results = []

    # Scroll to load all flights via lazy loading
    print("Loading all flights...")
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)
    prev_count = 0
    stable_rounds = 0
    for _ in range(60):
        driver.execute_script("window.scrollBy(0, 800);")
        time.sleep(1)
        # Stop as soon as a non-nonstop card is visible — all nonstops above it are already loaded
        found_nonstop_end = driver.execute_script("""
            var headers = document.querySelectorAll('[class*="flightHeaderRight"]');
            for (var i = 0; i < headers.length; i++) {
                var text = (headers[i].innerText || headers[i].textContent || '').trim().toUpperCase();
                if (text !== 'NONSTOP') return true;
            }
            return false;
        """)
        if found_nonstop_end:
            break
        count = len(driver.find_elements(By.XPATH,
            '//button[translate(normalize-space(.),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="details"]'
        ))
        if count != prev_count:
            stable_rounds = 0
            prev_count = count
        else:
            stable_rounds += 1
            if stable_rounds >= 5:
                break

    details_buttons = driver.find_elements(By.XPATH,
        '//button[translate(normalize-space(.),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="details"]'
    )
    print(f"Found {len(details_buttons)} flight(s).")

    # Filter to nonstop buttons only, stopping at the first non-nonstop flight
    nonstop_buttons = driver.execute_script("""
        var buttons = arguments[0];
        var result = [];
        for (var i = 0; i < buttons.length; i++) {
            var el = buttons[i];
            var found = false;
            for (var j = 0; j < 20; j++) {
                el = el.parentElement;
                if (!el) break;
                var headerRight = el.querySelector('[class*="flightHeaderRight"]');
                if (headerRight) {
                    var text = (headerRight.innerText || headerRight.textContent || '').trim().toUpperCase();
                    if (text === 'NONSTOP') {
                        result.push(buttons[i]);
                        found = true;
                    }
                    break;
                }
            }
            if (!found) break;
        }
        return result;
    """, details_buttons)
    print(f"Opening {len(nonstop_buttons)} nonstop details panels simultaneously...")
    for btn in nonstop_buttons:
        driver.execute_script("arguments[0].click();", btn)

    # Wait until fareClasses count matches the number of panels opened
    print("Waiting for panels to load...")
    expected = len(nonstop_buttons)
    fare_count = 0
    for _ in range(60):
        fare_count = len(driver.find_elements(By.CSS_SELECTOR, "[class*='fareClasses']"))
        if fare_count >= expected:
            break
        time.sleep(1)
    print(f"Total fareClasses elements loaded: {fare_count}")

    # Batch-extract all fare data in a single JS call — no per-element scrollIntoView or waits
    print("Extracting fare data...")
    raw = driver.execute_script("""
        var buttons = arguments[0];
        var out = [];
        for (var i = 0; i < buttons.length; i++) {
            var el = buttons[i];
            var container = null;
            for (var j = 0; j < 20; j++) {
                el = el.parentElement;
                if (!el) break;
                if (el.querySelectorAll('[class*="fareClasses"]').length > 0) {
                    container = el;
                    break;
                }
            }
            if (!container) { out.push(null); continue; }
            var fareEls = container.querySelectorAll('[class*="fareClasses"]');
            var aircraftEls = container.querySelectorAll('[class*="aircraftInfo"]');
            var departEl = container.querySelector('[class*="departTime"] [class*="time"]');
            var arrivalEl = container.querySelector('[class*="arrivalTime"] [class*="time"]');
            var depart = departEl ? (departEl.innerText || departEl.textContent || '').trim() : '';
            var arrival = arrivalEl ? (arrivalEl.innerText || arrivalEl.textContent || '').trim() : '';
            var segs = [];
            for (var k = 0; k < fareEls.length; k++) {
                segs.push({
                    fare: fareEls[k].innerText || fareEls[k].textContent || '',
                    aircraft: k < aircraftEls.length
                        ? (aircraftEls[k].innerText || aircraftEls[k].textContent || '')
                        : '',
                    depart: k === 0 ? depart : '',
                    arrival: k === 0 ? arrival : ''
                });
            }
            out.push(segs);
        }
        return out;
    """, nonstop_buttons)

    for i, segs in enumerate(raw):
        if not segs:
            print(f"  Flight {i + 1}: could not find container with fare classes.")
            continue
        segments = []
        for seg in segs:
            classes = parse_fare_classes(seg['fare'])
            if not classes:
                continue
            segments.append({
                "flight": seg['aircraft'].strip() or f"Segment {len(segments) + 1}",
                "classes": classes,
                "depart": seg.get('depart', ''),
                "arrival": seg.get('arrival', '')
            })
        if segments:
            results.append({"segments": segments})
        else:
            print(f"  Flight {i + 1}: no fare classes found in any segment.")

    return results


def main():
    parser = argparse.ArgumentParser(description="Scrape United fare class availability (batch JS extraction).")
    parser.add_argument("--origin",      required=True, help="Origin IATA code (e.g. ORD)")
    parser.add_argument("--destination", required=True, help="Destination IATA code (e.g. LAX)")
    parser.add_argument("--date",        required=True, help="Departure date YYYY-MM-DD")
    parser.add_argument("--end-date",    help="End date YYYY-MM-DD — scrapes each date in range via separate tabs")
    parser.add_argument("--return-date", help="Return date YYYY-MM-DD (round trip)")
    parser.add_argument("--filter",      help="Only show flights with >0 availability in this class (e.g. PZ)")
    parser.add_argument("--username",    help="MileagePlus username")
    parser.add_argument("--password",    help="MileagePlus password")
    args = parser.parse_args()

    fare_filter = args.filter.upper() if args.filter else None
    return_date = args.return_date if args.return_date else None
    origin      = args.origin.upper()
    destination = args.destination.upper()
    env = load_env()
    username = args.username or env.get("UNITED_USERNAME")
    password = args.password or env.get("UNITED_PASSWORD")

    # Build list of dates to scrape
    start_dt = datetime.strptime(args.date, "%Y-%m-%d")
    end_dt   = datetime.strptime(args.end_date, "%Y-%m-%d") if args.end_date else start_dt
    dates = []
    d = start_dt
    while d <= end_dt:
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    options = uc.ChromeOptions()
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-features=CalculateNativeWinOcclusion")
    driver = uc.Chrome(user_data_dir=PROFILE_DIR, headless=False, version_main=145, options=options)

    all_date_results = {}
    try:
        ensure_logged_in(driver, username, password)

        if len(dates) == 1:
            # Single date — original flow
            search(driver, origin, destination, dates[0], return_date)
            all_date_results[dates[0]] = scrape_results(driver)
        else:
            # Multi-date — open all tabs simultaneously, then process each
            print(f"Opening {len(dates)} tabs for dates {dates[0]} through {dates[-1]}...")
            tab_handles = []

            # Navigate first tab
            driver.get(get_search_url(origin, destination, dates[0], return_date))
            tab_handles.append((driver.current_window_handle, dates[0]))

            # Open remaining tabs without waiting
            for date_str in dates[1:]:
                url = get_search_url(origin, destination, date_str, return_date)
                driver.switch_to.new_window('tab')
                driver.get(url)
                tab_handles.append((driver.current_window_handle, date_str))

            # Process each tab sequentially
            for handle, date_str in tab_handles:
                driver.switch_to.window(handle)
                print(f"\nProcessing {date_str}...")
                try:
                    WebDriverWait(driver, 60).until(
                        lambda drv: len(drv.find_elements(By.CSS_SELECTOR, '[class*="flightHeaderRight"]')) > 0
                    )
                    time.sleep(2)
                    print("Results loaded.")
                    all_date_results[date_str] = scrape_results(driver)
                except TimeoutException:
                    print(f"Timed out waiting for results on {date_str}.")
                    all_date_results[date_str] = []
    finally:
        driver.quit()

    # Save and display results per date
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for date_str in dates:
        results = all_date_results.get(date_str, [])
        suffix = f"_{return_date}" if return_date else ""
        out_file = os.path.join(base_dir, f"results_{origin}_{destination}_{date_str}{suffix}.json")
        with open(out_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n{'=' * 52}")
        print(f"  {date_str}: {len(results)} flight(s) — saved to {out_file}")
        if results:
            shown = format_results(results, fare_filter)
            if fare_filter:
                print(f"  {shown}/{len(results)} flight(s) have {fare_filter} availability.")


if __name__ == "__main__":
    main()
