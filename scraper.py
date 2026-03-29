"""
Threads Post Reply Scraper
==========================
Uses Playwright network interception to capture GraphQL API responses
instead of fragile CSS selectors. Meta randomizes class names, but the
underlying API payloads are stable.

Usage:
    python scraper.py <threads_post_url> [--output replies.csv] [--max-scrolls 30]

Example:
    python scraper.py "https://www.threads.net/@zuck/post/ABC123"
"""

import argparse
import json
import logging
import random
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

GRAPHQL_URL_PATTERN = re.compile(r"threads\.(net|com)/(api/)?graphql")
REPLY_FIELDS = ["username", "text", "timestamp"]
_MAX_WALK_DEPTH = 20
_MAX_IDLE_SCROLLS = 4


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def _extract_replies_from_graphql(payload: dict) -> list[dict]:
    """Recursively walk the GraphQL JSON to find reply nodes."""
    replies = []

    def _walk(obj, depth=0):
        if depth > _MAX_WALK_DEPTH:
            return
        if isinstance(obj, dict):
            # Threads GraphQL reply nodes contain a "text_post_app_reply" or
            # nested "post" objects with "text_post_app_info".
            # The actual text lives under node -> thread_items -> post -> caption -> text
            # and the user under post -> user -> username.
            if "thread_items" in obj:
                for item in obj["thread_items"]:
                    reply = _parse_thread_item(item)
                    if reply:
                        replies.append(reply)
            for value in obj.values():
                _walk(value, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item, depth + 1)

    _walk(payload)
    return replies


def _parse_thread_item(item: dict) -> dict | None:
    """Extract username, text, and timestamp from a single thread_item."""
    post = item.get("post") or item.get("node", {}).get("post")
    if not post:
        return None

    # Username
    user = post.get("user", {})
    username = user.get("username", "")

    # Text – may be in caption.text or text_post_app_info
    caption = post.get("caption") or {}
    text = caption.get("text", "")

    # Timestamp – taken_at is a Unix epoch
    taken_at = post.get("taken_at", 0)
    if taken_at:
        ts = datetime.fromtimestamp(taken_at, tz=timezone.utc).isoformat()
    else:
        ts = ""

    if not text and not username:
        return None

    return {"username": username, "text": text, "timestamp": ts}


def _extract_replies_from_html_json(page) -> list[dict]:
    """
    Fallback: parse the hidden JSON payload embedded in <script> tags
    on initial page load (server-side rendered data).
    """
    replies = []
    try:
        scripts = page.query_selector_all("script[type='application/json']")
        for script in scripts:
            raw = script.inner_text()
            if not raw:
                continue
            try:
                data = json.loads(raw)
                found = _extract_replies_from_graphql(data)
                replies.extend(found)
            except json.JSONDecodeError:
                continue
    except Exception as exc:
        logger.debug("HTML JSON fallback failed: %s", exc)
    return replies


# ---------------------------------------------------------------------------
# Core scraper
# ---------------------------------------------------------------------------
def scrape_thread_replies(
    url: str,
    output_path: str = "replies.csv",
    max_scrolls: int = 30,
    headless: bool = False,
) -> pd.DataFrame:
    """
    Scrape replies from a public Threads post.

    Strategy:
    1. Intercept all GraphQL network responses and extract reply data.
    2. Scroll the page to trigger pagination / infinite-scroll loads.
    3. Fallback: parse embedded <script type="application/json"> blobs.
    """
    parsed_url = urlparse(url)
    is_threads = "threads.net" in parsed_url.netloc or "threads.com" in parsed_url.netloc
    if parsed_url.scheme not in ("http", "https") or not is_threads:
        raise ValueError(f"URL must be a threads.net/threads.com https URL, got: {url!r}")

    all_replies: list[dict] = []
    seen_keys: set[str] = set()

    def _add_reply(reply: dict) -> bool:
        """Deduplicate and store a reply. Returns True if new."""
        key = f"{reply['username']}:{reply['text'][:80]}"
        if key in seen_keys:
            return False
        seen_keys.add(key)
        all_replies.append(reply)
        return True

    def _on_response(response):
        """Callback for every network response."""
        try:
            if not GRAPHQL_URL_PATTERN.search(response.url):
                return
            if "application/json" not in (response.headers.get("content-type", "")):
                return
            body = response.json()
            found = _extract_replies_from_graphql(body)
            for r in found:
                if _add_reply(r):
                    logger.info("  [+] @%s: %s...", r["username"], r["text"][:60])
        except Exception as exc:
            logger.warning("Response parse error (%s): %s", response.url, exc)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/Los_Angeles",
        )
        # Remove the navigator.webdriver flag
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = context.new_page()
        page.on("response", _on_response)

        logger.info("[*] Navigating to %s", url)
        page.goto(url, wait_until="networkidle", timeout=60_000)
        logger.info("[*] Page loaded. Starting scroll loop (max %d scrolls)...", max_scrolls)

        # --- Fallback: extract from embedded JSON on initial load ---
        for r in _extract_replies_from_html_json(page):
            _add_reply(r)

        # --- Infinite scroll to load more replies ---
        prev_count = 0
        no_new_count = 0
        for i in range(max_scrolls):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            delay = random.uniform(1.5, 4.5)
            logger.info(
                "  [scroll %d/%d] replies so far: %d | waiting %.1fs",
                i + 1, max_scrolls, len(all_replies), delay,
            )
            page.wait_for_timeout(delay * 1000)

            # Check if we got new replies
            if len(all_replies) == prev_count:
                no_new_count += 1
                if no_new_count >= _MAX_IDLE_SCROLLS:
                    logger.info("[*] No new replies after %d consecutive scrolls. Stopping.", _MAX_IDLE_SCROLLS)
                    break
            else:
                no_new_count = 0
            prev_count = len(all_replies)

        browser.close()

    # --- Build DataFrame & save ---
    if not all_replies:
        logger.warning(
            "[!] No replies captured. The post may have no replies, "
            "or Meta's API structure may have changed. "
            "Try running in non-headless mode to verify the page loads correctly."
        )
        df = pd.DataFrame(columns=REPLY_FIELDS)
    else:
        df = (
            pd.DataFrame(all_replies, columns=REPLY_FIELDS)
            .drop_duplicates(subset=["username", "text"])
            .reset_index(drop=True)
        )

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info("[*] Done! %d replies saved to %s", len(df), output_path)
    return df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(
        description="Scrape replies from a public Threads post."
    )
    parser.add_argument("url", help="Full URL of the Threads post")
    parser.add_argument(
        "--output", "-o", default="replies.csv", help="Output CSV path (default: replies.csv)"
    )
    parser.add_argument(
        "--max-scrolls",
        type=int,
        default=30,
        help="Maximum scroll iterations (default: 30)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (not recommended for anti-detection)",
    )
    args = parser.parse_args()

    scrape_thread_replies(
        url=args.url,
        output_path=args.output,
        max_scrolls=args.max_scrolls,
        headless=args.headless,
    )


if __name__ == "__main__":
    main()
