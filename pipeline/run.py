"""Single entry point: scrape -> normalize."""
from __future__ import annotations

import scrape
import normalize


def main() -> None:
    scrape.main()
    normalize.main()


if __name__ == "__main__":
    main()
