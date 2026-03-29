<p align="center">
  <h1 align="center">Thread Analyzer MCP Server</h1>
  <p align="center">
    Scrape and analyze replies from any public Threads post — right from your AI coding agent.
  </p>
</p>

<p align="center">
  <a href="https://github.com/ethan-tsai-tsai/thread-analyzer/blob/main/LICENSE"><img src="https://img.shields.io/github/license/ethan-tsai-tsai/thread-analyzer" alt="License" /></a>
  <a href="https://github.com/ethan-tsai-tsai/thread-analyzer/stargazers"><img src="https://img.shields.io/github/stars/ethan-tsai-tsai/thread-analyzer" alt="Stars" /></a>
  <a href="https://pypi.org/project/thread-analyzer/"><img src="https://img.shields.io/pypi/v/thread-analyzer" alt="PyPI" /></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.13+-blue.svg" alt="Python 3.13+" /></a>
</p>

---

## What is this?

An MCP server that lets your AI assistant scrape a Threads post URL, then query and analyze the replies — all through natural conversation.

**Instead of:**
```
1. Manually open browser
2. Scroll through hundreds of replies
3. Copy-paste into spreadsheet
4. Manually look for patterns
```

**Just say:**
> "Analyze the replies on this Threads post: https://www.threads.com/@zuck/post/ABC123"

Your AI agent handles the rest.

## Features

- **Network interception** — Captures GraphQL API responses, not fragile CSS selectors that Meta randomizes
- **Anti-detection** — Randomized scroll delays, stealth browser flags, custom User-Agent
- **4 MCP tools** — Scrape, list, search, and get statistics on replies
- **Works with any MCP client** — Claude Code, Claude Desktop, Cursor, VS Code, Windsurf, and more

## MCP Tools

| Tool | Description |
|------|-------------|
| `scrape_thread(url)` | Scrape all replies from a public Threads post |
| `get_all_replies()` | Return all scraped replies with username and timestamp |
| `search_replies(keyword)` | Case-insensitive keyword search across replies |
| `get_reply_stats()` | Reply count, top commenters, avg length, time range |

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
git clone https://github.com/ethan-tsai-tsai/thread-analyzer.git
cd thread-analyzer
uv sync
uv run playwright install chromium
```

### Configuration

Add the server to your MCP client config:

```json
{
  "mcpServers": {
    "thread-analyzer": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/thread-analyzer", "python", "server.py"]
    }
  }
}
```

<details>
<summary><strong>Claude Code</strong></summary>

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "thread-analyzer": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/thread-analyzer", "python", "server.py"]
    }
  }
}
```

Or run: `claude mcp add thread-analyzer -- uv run --directory /absolute/path/to/thread-analyzer python server.py`

</details>

<details>
<summary><strong>Claude Desktop</strong></summary>

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "thread-analyzer": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/thread-analyzer", "python", "server.py"]
    }
  }
}
```

</details>

<details>
<summary><strong>Cursor</strong></summary>

Go to **Cursor Settings > MCP > Add new MCP Server**, then add:

```json
{
  "mcpServers": {
    "thread-analyzer": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/thread-analyzer", "python", "server.py"]
    }
  }
}
```

</details>

<details>
<summary><strong>VS Code (Copilot)</strong></summary>

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "thread-analyzer": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/thread-analyzer", "python", "server.py"]
    }
  }
}
```

</details>

<details>
<summary><strong>Windsurf</strong></summary>

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "thread-analyzer": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/thread-analyzer", "python", "server.py"]
    }
  }
}
```

</details>

### Standalone CLI

You can also use the scraper directly without MCP:

```bash
uv run python scraper.py "https://www.threads.com/@user/post/XXXXX"

# Options
uv run python scraper.py "URL" --output custom.csv --max-scrolls 50
```

## How It Works

```
┌─────────────┐     MCP (stdio)     ┌──────────────┐    Playwright    ┌─────────────┐
│  AI Client  │ ◄──────────────────► │  server.py   │ ◄──────────────► │  Threads.com │
│ (Claude,    │   scrape_thread()    │  (FastMCP)   │   GraphQL API   │  (Meta)      │
│  Cursor...) │   get_all_replies()  │              │   interception  │              │
│             │   search_replies()   │  replies.csv │                 │              │
│             │   get_reply_stats()  │              │                 │              │
└─────────────┘                      └──────────────┘                 └─────────────┘
```

1. **You** give your AI assistant a Threads post URL
2. **AI** calls `scrape_thread(url)` via MCP
3. **Server** launches headless Chromium, navigates to the post
4. **Playwright** intercepts GraphQL network responses containing reply data
5. **Server** parses replies (username, text, timestamp), saves to CSV
6. **AI** uses `get_all_replies()`, `search_replies()`, `get_reply_stats()` to analyze

## Anti-Detection

| Technique | Purpose |
|-----------|---------|
| Custom User-Agent | Mimics real Chrome browser |
| `navigator.webdriver` removal | Hides automation flag |
| `AutomationControlled` disabled | Prevents Chromium detection |
| Randomized scroll delays (1.5-4.5s) | Avoids behavioral fingerprinting |
| Early stop on idle scrolls | Mimics natural browsing patterns |

## Limitations

- **Public posts only** — Cannot access private or restricted posts
- **Meta's anti-bot measures** — Meta may block headless browsers; if scraping fails, try the standalone CLI in non-headless mode
- **GraphQL schema changes** — Meta periodically changes their API structure; the parser in `scraper.py` may need updating

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

[MIT](LICENSE)

---

<p align="center">
  <a href="https://star-history.com/#ethan-tsai-tsai/thread-analyzer">
    <img src="https://api.star-history.com/svg?repos=ethan-tsai-tsai/thread-analyzer&type=Date" alt="Star History Chart" width="600" />
  </a>
</p>
