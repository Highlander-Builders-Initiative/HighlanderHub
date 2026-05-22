
## 2026-05-22 - Precompute event search text for filtering
**Learning:** Rebuilding and lowercasing the event search string for every item on every keystroke was a repeat-cost hot path in /events.
**Action:** Cache the normalized search blob per loaded batch and keep query checks to simple substring tests.
