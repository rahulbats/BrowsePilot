"""Copilot SDK tool definitions that expose Playwright browser actions to the agent."""

from pydantic import BaseModel, Field
from copilot import define_tool
from .controller import BrowserController
from telemetry import log_discrepancy, is_enabled as telemetry_enabled


# Shared browser instance
_browser: BrowserController | None = None


def get_browser() -> BrowserController:
    return _browser


def init_browser(browser_id: str = "msedge") -> BrowserController:
    global _browser
    _browser = BrowserController(browser_id=browser_id)
    return _browser


class NavigateParams(BaseModel):
    url: str = Field(description="The URL to navigate to (e.g. 'https://portal.azure.com')")


@define_tool(
    name="browser_navigate",
    description="Open a real browser window and navigate to a URL. Use this when you need to visit a website to get current, accurate information. The user can see this browser window.",
)
async def browser_navigate(params: NavigateParams) -> str:
    title = await _browser.navigate(params.url)
    return f"Navigated to: {title} ({params.url})"


@define_tool(
    name="browser_read_page",
    description="Read the text content of the current page in the browser. Use this to see what's actually on the page right now, instead of relying on training data which may be outdated.",
)
async def browser_read_page() -> str:
    return await _browser.get_page_content()


@define_tool(
    name="browser_list_elements",
    description="List all interactive elements on the current page (buttons, links, inputs, tabs). Use this to find specific UI elements the user should click or interact with.",
)
async def browser_list_elements() -> str:
    return await _browser.get_interactive_elements()


class ClickParams(BaseModel):
    selector: str = Field(description="CSS selector (e.g. '#submit-btn', '.nav-link') or visible text of the element to click")


@define_tool(
    name="browser_click",
    description="Click an element on the page by CSS selector or visible text. Use this to navigate menus, click buttons, or interact with the page on behalf of the user.",
)
async def browser_click(params: ClickParams) -> str:
    return await _browser.click(params.selector)


class FillParams(BaseModel):
    selector: str = Field(description="CSS selector of the input field to fill")
    value: str = Field(description="The text value to type into the field")


@define_tool(
    name="browser_fill",
    description="Fill a form field (input, textarea) with a value. Use this to help the user fill out forms on web pages.",
)
async def browser_fill(params: FillParams) -> str:
    return await _browser.fill(params.selector, params.value)


class SelectParams(BaseModel):
    selector: str = Field(description="CSS selector of the dropdown, or the visible label/placeholder text of the dropdown (e.g. 'State', 'Country', '#state-select')")
    value: str = Field(description="The option text to select (e.g. 'Texas', 'United States'). Use the exact visible text of the option.")


@define_tool(
    name="browser_select",
    description="Select an option from a dropdown menu. Works with both native HTML <select> elements and custom dropdowns (like those in Azure Portal, React, etc.). Pass the dropdown identifier and the option text you want to select. It will click to open the dropdown, scroll to find the option, and select it.",
)
async def browser_select(params: SelectParams) -> str:
    return await _browser.select_option(params.selector, params.value)


class HighlightParams(BaseModel):
    selector: str = Field(description="CSS selector OR visible text to find and highlight. Prefer using the exact visible text from the page (e.g. '$150.00 credits remaining') rather than CSS selectors, since text matching is more reliable on complex pages.")


@define_tool(
    name="browser_highlight",
    description="Highlight an element on the page with a red border and scroll it into view. Accepts a CSS selector OR visible text from the page. Text-based matching is preferred for complex sites like Azure Portal — just pass the text you see on the page and it will find and highlight the right element.",
)
async def browser_highlight(params: HighlightParams) -> str:
    return await _browser.highlight(params.selector)


@define_tool(
    name="browser_screenshot",
    description="Take a screenshot of the current browser page and open it for the user. ONLY use this when the user explicitly asks for a screenshot. Do NOT use this proactively.",
)
async def browser_screenshot() -> str:
    return await _browser.screenshot()


@define_tool(
    name="browser_go_back",
    description="Navigate back to the previous page in browser history.",
)
async def browser_go_back() -> str:
    return await _browser.go_back()


@define_tool(
    name="browser_get_url",
    description="Get the current URL of the browser page.",
)
async def browser_get_url() -> str:
    return await _browser.get_url()


class DiscrepancyParams(BaseModel):
    expected: str = Field(description="What you expected to find on the page (e.g. 'A button labeled All Services in the left sidebar')")
    actual: str = Field(description="What you actually found instead (e.g. 'No All Services button exists. There is a search bar and a hamburger menu instead')")
    category: str = Field(
        default="ui_discrepancy",
        description="Category of discrepancy: 'outdated_link', 'missing_element', 'ui_discrepancy', 'changed_layout', or 'stale_docs'",
    )


@define_tool(
    name="report_discrepancy",
    description="Report a UI discrepancy — when you expected something on a page but found something different. Use this when: (1) a link or URL leads to an unexpected page, (2) a button/menu mentioned in docs doesn't exist, (3) the UI layout has changed from what was expected. This helps backend teams improve docs and AI training data. Only call this if the user consented to telemetry.",
)
async def report_discrepancy(params: DiscrepancyParams) -> str:
    if not telemetry_enabled():
        return "Telemetry is disabled — discrepancy not logged. You can still tell the user about the issue."

    url = await _browser.get_url() if _browser else "unknown"
    result = log_discrepancy(
        url=url,
        expected=params.expected,
        actual=params.actual,
        category=params.category,
    )
    return f"Discrepancy logged: {params.category} at {url}. Expected: '{params.expected}' → Found: '{params.actual}'"


def create_browser_tools() -> list:
    """Return all browser tools for use in a Copilot SDK session."""
    return [
        browser_navigate,
        browser_read_page,
        browser_list_elements,
        browser_click,
        browser_fill,
        browser_select,
        browser_highlight,
        browser_screenshot,
        browser_go_back,
        browser_get_url,
        report_discrepancy,
    ]
