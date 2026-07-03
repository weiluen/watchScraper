"""Fetch one image per priced reference from Chrono24 search results.

Searches "{brand} {ref}" and prefers a listing card whose text actually
contains the reference (normalized), so a generic search result can't hand
us the wrong variant. Saves to static/img/refs/{ref_slug}.jpg; the web app
falls back to the family image when a reference image is missing.
"""

import logging
import random
import re
import sys
import time
import warnings
from pathlib import Path
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
warnings.filterwarnings("ignore")

from watchscraper.analysis import build_clean_dataset, reference_values  # noqa: E402
from watchscraper.database import engine  # noqa: E402
from watchscraper.web.services import ref_slug  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "watchscraper" / "web" / "static" / "img" / "refs"
)
SEARCH_URL = "https://www.chrono24.com/search/index.htm?query={query}&dosearch=true"
IMG_WIDTH = "440"


def _norm(text: str) -> str:
    return re.sub(r"[\s.\-/]", "", text).upper()


def find_image_url(html: str, ref: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.js-listing-item-container")
    ref_n = _norm(ref)

    def image_of(card):
        img = card.select_one("img[data-lazy-sweet-spot-master-src]")
        return img["data-lazy-sweet-spot-master-src"].replace("_SIZE_", IMG_WIDTH) if img else None

    # Prefer a card that mentions the reference explicitly
    for card in cards:
        if ref_n in _norm(card.get_text(" ", strip=True)):
            url = image_of(card)
            if url:
                return url
    # Otherwise trust Chrono24's ref search and take the first card with an image
    for card in cards[:3]:
        url = image_of(card)
        if url:
            return url
    return None


def fetch_ref_image(brand: str, ref: str, dial: str | None = None) -> bool:
    slug = ref_slug(brand, ref, dial)
    out_path = OUT_DIR / f"{slug}.jpg"
    if out_path.exists():
        return True

    query = f"{brand} {ref} {dial} dial" if dial else f"{brand} {ref}"
    url = SEARCH_URL.format(query=quote_plus(query))
    try:
        resp = cffi.get(url, impersonate="chrome", timeout=30)
    except Exception:
        logger.exception("%s %s: search failed", brand, ref)
        return False
    if resp.status_code != 200:
        logger.warning("%s %s: HTTP %d", brand, ref, resp.status_code)
        return False

    img_url = find_image_url(resp.text, ref)
    if not img_url:
        logger.warning("%s %s: no image found", brand, ref)
        return False

    try:
        img_resp = cffi.get(img_url, impersonate="chrome", timeout=30)
    except Exception:
        logger.exception("%s %s: image download failed", brand, ref)
        return False
    if img_resp.status_code != 200 or len(img_resp.content) < 2000:
        logger.warning("%s %s: bad image response", brand, ref)
        return False

    out_path.write_bytes(img_resp.content)
    logger.info("%s %s -> %s (%.0f KB)", brand, ref, out_path.name, len(img_resp.content) / 1024)
    return True


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = build_clean_dataset(engine)
    refs = reference_values(df)
    logger.info("Fetching images for %d priced references", len(refs))

    import pandas as pd

    got, missed = 0, 0
    for _, r in refs.iterrows():
        dial = r.get("dial_variant")
        dial = dial if (dial and pd.notna(dial)) else None
        if fetch_ref_image(r["brand"], r["ref"], dial):
            got += 1
        else:
            missed += 1
        time.sleep(1.2 + random.random() * 1.3)
    logger.info("Done: %d images, %d missing (family image fallback covers those)", got, missed)


if __name__ == "__main__":
    main()
