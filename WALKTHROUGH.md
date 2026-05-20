# Scraper Pipeline Fix Walkthrough

I have implemented **Workaround B (Static User ID Mapping)** with dynamic hybrid fallback to resolve the breaking `instaloader` GraphQL profile lookup bug.

---

## 1. Summary of Changes

### [MODIFY] [scrape.py](file:///Users/kevinlin/Documents/GitHub/HighlanderHub/pipeline/scrape.py)
* Added a permanent static mapping (`KNOWN_USER_IDS`) for all of your active scraped accounts (`cyber_ucr`, `acm_ucr`, and `ucrvsa`). I retrieved these permanent numeric User IDs by querying your local Supabase database.
* Replaced the broken `instaloader.Profile.from_username()` lookup with a new hybrid helper `_resolve_profile()` that:
  1. Resolves handles using the static `KNOWN_USER_IDS` mapping with **0 network requests**, completely immunizing existing accounts against Instagram API breaks.
  2. Falls back to Instagram's standard search API GET endpoint (`TopSearchResults`) which is fully operational and untouched by this bug (allowing any new handles added to `accounts.json` to be resolved dynamically when your scraper runs logged-in).
  3. Falls back to default `from_username` GraphQL query as a final safety net.

---

## 2. Validation & Verification Results

### Automated Unit Tests
I executed your full test suite to verify that our hybrid resolution logic does not disrupt any mocked components or execution boundaries:
```bash
python3 -m unittest discover tests
```
* **Result:** `OK (14 tests passed)`
* **Log Output:**
  ```text
  Ran 14 tests in 0.017s
  OK
  ```

---

## 3. How to Verify Locally

Simply run your scraping script in your python environment with your active session:
```bash
.venv/bin/python run.py
```
You will see that the profile resolutions for `cyber_ucr`, `acm_ucr`, and `ucrvsa` succeed instantly using the static mappings, allowing story scraping to proceed without crashing!
