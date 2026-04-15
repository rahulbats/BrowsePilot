# BrowsePilot Agent

BrowsePilot is an AI-powered **browser co-pilot** that uses Playwright to drive a
real, headed browser window on the user's machine. It is designed to be used
from Copilot Chat (CLI or VS Code) as `@BrowsePilot`, or directly via the
Python CLI (`python src/main.py`).

## Purpose

- Help users navigate complex web portals (Azure Portal, M365 Admin Center,
  GitHub Enterprise, internal apps) with **live, UI-grounded guidance**.
- Eliminate hallucinated "click the button that no longer exists" instructions
  by always reading the **current DOM**.
- Keep the user in control: the browser is visible and interactive at all
  times; the agent is a co-pilot, not an autonomous bot.

## System Behavior

The core system prompt (used in the CLI entrypoint) instructs the agent to:

- Always **navigate and read the page** before giving instructions.
- Refer to **exact UI text** (button labels, menu names) seen on the page.
- Prefer **visual guidance** (highlighting, scrolling into view) over long
  textual explanations.
- strictly follow safety rules:
  - Never click or submit anything on login / auth / consent / MFA pages.
  - Never accept permissions or consents on behalf of the user.
  - Never handle passwords, tokens, or other secrets.
  - Describe destructive actions (create / delete / modify) before acting and
    wait for explicit confirmation.

## Tools

BrowsePilot exposes the following tools (both via the GitHub Copilot SDK in
`src/browser/tools.py` and via MCP in `src/browsepilot_mcp.py`):

- `browser_connect(endpoint: str) -> str`  
  Connect to an already-running browser via Chrome DevTools Protocol (CDP).
  The browser must be started with `--remote-debugging-port=9222`. This lets
  BrowsePilot control tabs the user already has open.

- `browser_list_tabs() -> str`  
  List all open tabs in the connected browser with titles and URLs.

- `browser_switch_tab(tab_index | url_substring) -> str`  
  Switch to a different browser tab by index or partial URL match.

- `browser_navigate(url: str) -> str`  
  Open a real browser window and navigate to the given URL.

- `browser_read_page() -> str`  
  Read the visible text content of the current page (title, URL, body text)
  for grounded reasoning.

- `browser_list_elements() -> str`  
  List interactive elements (buttons, links, inputs, tabs) with labels and
  selector hints.

- `browser_click(selector: str) -> str`  
  Click an element by CSS selector or visible text.

- `browser_fill(selector: str, value: str) -> str`  
  Fill an input / textarea with the given value.

- `browser_select(selector: str, value: str) -> str`  
  Select an option from a dropdown, supporting both native `<select>` and
  custom JS dropdowns.

- `browser_highlight(selector_or_text: str) -> str`  
  Highlight an element with a red border and scroll it into view, using CSS or
  text-based matching.

- `browser_screenshot() -> str`  
  Capture a screenshot of the current page to a local file and open it for the
  user. Should only be used when the user explicitly asks for a screenshot.

- `browser_go_back() -> str`  
  Navigate back in browser history.

- `browser_get_url() -> str`  
  Return the current page URL.

- `report_discrepancy(expected: str, actual: str, category: str)`  
  Log UI discrepancies to Azure Application Insights when telemetry is
  enabled. Available in both the Copilot SDK CLI tools and the MCP server.

## Usage Paths

BrowsePilot can be used in two ways:

1. **CLI** (`python src/main.py`) — standalone terminal chat using the GitHub
   Copilot SDK. Interactive model/browser picker and telemetry opt-in at
   startup.
2. **MCP Server** (`@BrowsePilot`) — local MCP server for VS Code Copilot Chat
   or Copilot CLI. Automatically discovered via `mcp.json`. Telemetry is
   auto-enabled when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set in the
   environment or in `mcp.json`'s `"env"` block.

Both paths share the same `BrowserController`, browser tools, persistent
browser profile (Entra ID SSO), and telemetry module.

## MCP Server

The MCP implementation lives in `src/browsepilot_mcp.py` and is configured via
`mcp.json` at the repo root. It:

- Runs on the **local machine** and uses Playwright to control Edge/Chrome.
- Exposes all browser_* tools listed above **plus** `report_discrepancy` over
  the Model Context Protocol.
- Shares a single `BrowserController` instance per process with a persistent
  profile directory so Entra SSO and cookies are reused across sessions.
- Auto-enables telemetry when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set.
  To configure it in `mcp.json`:

  ```json
  "env": {
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=...;IngestionEndpoint=..."
  }
  ```

To use it with Copilot CLI or VS Code, point your MCP configuration to this
repo and ensure the `mcp.json` file is discovered (for Copilot CLI, the repo
can be added as a local MCP source).
