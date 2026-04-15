"""BrowsePilot MCP server exposing local browser tools for Copilot CLI / VS Code.

This server runs on the user's machine and uses Playwright to control a real
headed browser window. It exposes a small set of tools over the Model Context
Protocol (MCP) so you can use it as `@BrowsePilot` from Copilot Chat.
"""

import asyncio
import atexit
import os
import sys
from typing import Optional

# Ensure src/ is on the path when run from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from browser.controller import BrowserController
import telemetry


mcp = FastMCP("browsepilot")

# Auto-enable telemetry when the connection string is provided via env / mcp.json.
if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    telemetry.set_consent(True)

# Single shared browser controller for the process.
_browser: Optional[BrowserController] = None


def get_browser() -> BrowserController:
    global _browser
    if _browser is None:
        # Default to Edge; users can change default via env vars used inside
        # BrowserController if needed.
        _browser = BrowserController(browser_id="msedge")
    return _browser


async def _ensure_browser_launched() -> BrowserController:
    browser = get_browser()
    # BrowserController.launch is idempotent if already open.
    await browser.launch()
    return browser


@mcp.tool()
async def browser_connect(endpoint: str = "http://localhost:9222") -> str:
    """Connect to an already-running browser via Chrome DevTools Protocol (CDP).

    The target browser must have been started with --remote-debugging-port=9222
    (or whatever port you specify). This lets BrowsePilot control tabs the user
    already has open instead of launching a new browser window.

    Example: start Edge with  msedge --remote-debugging-port=9222
    """

    browser = get_browser()
    return await browser.connect_cdp(endpoint)


@mcp.tool()
async def browser_list_tabs() -> str:
    """List all open tabs in the connected browser with their titles and URLs.

    The currently active tab is marked with an arrow.
    """

    browser = get_browser()
    return await browser.list_pages()


@mcp.tool()
async def browser_switch_tab(tab_index: int = -1, url_substring: str = "") -> str:
    """Switch to a different browser tab by its index number or by a URL substring.

    Use browser_list_tabs first to see available tabs and their indices.
    Provide either tab_index (0-based) or url_substring (partial URL match).
    """

    browser = get_browser()
    idx = tab_index if tab_index >= 0 else None
    url = url_substring if url_substring else None
    return await browser.switch_to_page(tab_index=idx, url_substring=url)


@mcp.tool()
async def browser_navigate(url: str) -> str:
    """Open a real browser window and navigate to a URL.

    Use this when you need to visit a website to get current, accurate
    information. The user can see this browser window.
    """

    browser = await _ensure_browser_launched()
    title = await browser.navigate(url)
    current_url = await browser.get_url()
    return f"Navigated to: {title} ({current_url})"


@mcp.tool()
async def browser_read_page() -> str:
    """Read the text content of the current page in the browser.

    Use this to see what's actually on the page right now, instead of relying
    on training data which may be outdated.
    """

    browser = await _ensure_browser_launched()
    return await browser.get_page_content()


@mcp.tool()
async def browser_list_elements() -> str:
    """List interactive elements (buttons, links, inputs, tabs) on the page.

    Use this to find specific UI elements the user should click or interact
    with.
    """

    browser = await _ensure_browser_launched()
    return await browser.get_interactive_elements()


@mcp.tool()
async def browser_click(selector: str) -> str:
    """Click an element by CSS selector or visible text on the page."""

    browser = await _ensure_browser_launched()
    return await browser.click(selector)


@mcp.tool()
async def browser_fill(selector: str, value: str) -> str:
    """Fill a form field (input, textarea) with a value."""

    browser = await _ensure_browser_launched()
    return await browser.fill(selector, value)


@mcp.tool()
async def browser_select(selector: str, value: str) -> str:
    """Select an option from a dropdown menu by visible text."""

    browser = await _ensure_browser_launched()
    return await browser.select_option(selector, value)


@mcp.tool()
async def browser_highlight(selector_or_text: str) -> str:
    """Highlight an element on the page with a red border and scroll it into view.

    Accepts a CSS selector OR visible text from the page. Text-based matching is
    preferred for complex sites like Azure Portal.
    """

    browser = await _ensure_browser_launched()
    return await browser.highlight(selector_or_text)


@mcp.tool()
async def browser_screenshot() -> str:
    """Take a screenshot of the current page and open it for the user.

    ONLY use this when the user explicitly asks for a screenshot. Do NOT use
    this proactively.
    """

    browser = await _ensure_browser_launched()
    return await browser.screenshot()


@mcp.tool()
async def browser_go_back() -> str:
    """Navigate back to the previous page in browser history."""

    browser = await _ensure_browser_launched()
    return await browser.go_back()


@mcp.tool()
async def browser_get_url() -> str:
    """Get the current URL of the browser page."""

    browser = await _ensure_browser_launched()
    return await browser.get_url()


@mcp.tool()
async def report_discrepancy(expected: str, actual: str, category: str = "ui_discrepancy") -> str:
    """Report a UI discrepancy when you expected something on a page but found something different.

    Use this when: (1) a link or URL leads to an unexpected page, (2) a button
    or menu mentioned in docs doesn't exist, (3) the UI layout has changed from
    what was expected.  This helps backend teams improve docs and AI training data.

    Categories: 'outdated_link', 'missing_element', 'ui_discrepancy',
    'changed_layout', or 'stale_docs'.
    """

    if not telemetry.is_enabled():
        return (
            "Telemetry is disabled — discrepancy not logged. "
            "Set APPLICATIONINSIGHTS_CONNECTION_STRING in the environment "
            "or in mcp.json to enable it."
        )

    url = "unknown"
    try:
        browser = get_browser()
        if browser.is_open:
            url = await browser.get_url()
    except Exception:
        pass

    result = telemetry.log_discrepancy(
        url=url,
        expected=expected,
        actual=actual,
        category=category,
    )
    return (
        f"Discrepancy logged: {category} at {url}. "
        f"Expected: '{expected}' → Found: '{actual}'"
    )


async def _shutdown_browser() -> None:
    """Best-effort cleanup for the browser when the server exits."""

    global _browser
    if _browser is not None:
        try:
            await _browser.close()
        except Exception:
            # Best-effort; Playwright may already have been torn down.
            pass
        _browser = None


def _on_exit() -> None:
    # Run async cleanup in a fresh event loop when the process is exiting.
    try:
        asyncio.run(_shutdown_browser())
    except Exception:
        pass


atexit.register(_on_exit)


if __name__ == "__main__":
    # FastMCP manages the MCP event loop on stdin/stdout.
    mcp.run()
