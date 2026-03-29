"""
Threads Replies MCP Server
===========================
A local MCP server that can scrape a Threads post URL, store the replies,
and provide search/analysis tools — all via MCP tools.

Run: python server.py
"""

import asyncio
import logging
from pathlib import Path

import pandas as pd
from mcp.server.fastmcp import FastMCP

from scraper import scrape_thread_replies

logger = logging.getLogger(__name__)

mcp = FastMCP("ThreadsDatabase")

CSV_PATH = Path(__file__).parent / "replies.csv"


def _load_replies() -> pd.DataFrame:
    """Load and clean the replies CSV."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            "No replies data yet. Use the scrape_thread tool first with a Threads post URL."
        )
    df = pd.read_csv(CSV_PATH)
    df = df.dropna(subset=["text"])
    df = df[df["text"].str.strip() != ""]
    return df.reset_index(drop=True)


def _format_replies(df: pd.DataFrame) -> str:
    """Format a DataFrame of replies into a readable string."""
    if df.empty:
        return "No replies found."
    lines = []
    for _, row in df.iterrows():
        ts = f" ({row['timestamp']})" if pd.notna(row.get("timestamp")) else ""
        lines.append(f"@{row['username']}{ts}: {row['text']}")
    return "\n".join(lines)


@mcp.tool()
async def scrape_thread(url: str, max_scrolls: int = 20) -> str:
    """Scrape replies from a public Threads post URL.

    Opens a browser, navigates to the post, intercepts GraphQL API responses
    to extract replies, and saves them locally. This must be called before
    using get_all_replies or search_replies.

    Args:
        url: Full URL of the Threads post (e.g. https://www.threads.com/@user/post/ABC123)
        max_scrolls: Maximum scroll iterations for loading more replies (default: 20)
    """
    try:
        df = await asyncio.to_thread(
            scrape_thread_replies,
            url=url,
            output_path=str(CSV_PATH),
            max_scrolls=max_scrolls,
            headless=True,
        )
        if df.empty:
            return (
                "Scraping completed but no replies were captured. "
                "The post may have no replies, or Meta may have blocked the request. "
                "Try again or use a different post URL."
            )
        return (
            f"Successfully scraped {len(df)} replies from:\n{url}\n\n"
            f"You can now use get_all_replies() or search_replies(keyword) to analyze them.\n\n"
            f"Preview (first 5):\n{_format_replies(df.head(5))}"
        )
    except ValueError as exc:
        return f"Invalid URL: {exc}"
    except Exception as exc:
        return f"Scraping failed: {exc}"


@mcp.tool()
def get_all_replies() -> str:
    """Get all scraped Threads replies.

    Returns a formatted list of all replies with username, timestamp and text.
    Call scrape_thread first if no data exists yet.
    """
    try:
        df = _load_replies()
        return f"Total replies: {len(df)}\n\n{_format_replies(df)}"
    except FileNotFoundError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error reading replies: {exc}"


@mcp.tool()
def search_replies(keyword: str) -> str:
    """Search Threads replies for a keyword (case-insensitive).

    Args:
        keyword: The search term to filter replies by.

    Returns matching replies with username and text.
    """
    try:
        df = _load_replies()
        mask = df["text"].str.contains(keyword, case=False, na=False)
        matches = df[mask]
        return (
            f"Found {len(matches)} replies matching '{keyword}':\n\n"
            f"{_format_replies(matches)}"
        )
    except FileNotFoundError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error searching replies: {exc}"


@mcp.tool()
def get_reply_stats() -> str:
    """Get statistics about the scraped replies.

    Returns reply count, unique users, most active commenters,
    and time range of replies.
    """
    try:
        df = _load_replies()
        total = len(df)
        unique_users = df["username"].nunique()

        # Most active commenters
        top_users = df["username"].value_counts().head(10)
        top_users_str = "\n".join(
            f"  @{user}: {count} replies" for user, count in top_users.items()
        )

        # Time range
        ts_col = pd.to_datetime(df["timestamp"], errors="coerce")
        valid_ts = ts_col.dropna()
        if not valid_ts.empty:
            time_range = f"{valid_ts.min().isoformat()} to {valid_ts.max().isoformat()}"
        else:
            time_range = "No timestamp data available"

        # Average reply length
        avg_len = df["text"].str.len().mean()

        return (
            f"Reply Statistics:\n"
            f"  Total replies: {total}\n"
            f"  Unique users: {unique_users}\n"
            f"  Avg reply length: {avg_len:.0f} characters\n"
            f"  Time range: {time_range}\n\n"
            f"Top commenters:\n{top_users_str}"
        )
    except FileNotFoundError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error computing stats: {exc}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    mcp.run(transport="stdio")
