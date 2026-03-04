"""Copilot SDK tool definitions that expose Playwright browser actions to the agent."""

from pydantic import BaseModel, Field
from copilot import define_tool
from .controller import BrowserController


# Shared browser instance
_browser = BrowserController()


def get_browser() -> BrowserController:
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


class HighlightParams(BaseModel):
    selector: str = Field(description="CSS selector of the element to highlight with a red border")


@define_tool(
    name="browser_highlight",
    description="Highlight an element on the page with a red border and scroll it into view. Use this to visually show the user which element to look at or click.",
)
async def browser_highlight(params: HighlightParams) -> str:
    return await _browser.highlight(params.selector)


@define_tool(
    name="browser_screenshot",
    description="Take a screenshot of the current browser page. Use this to capture the current state of the page.",
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


def create_browser_tools() -> list:
    """Return all browser tools for use in a Copilot SDK session."""
    return [
        browser_navigate,
        browser_read_page,
        browser_list_elements,
        browser_click,
        browser_fill,
        browser_highlight,
        browser_screenshot,
        browser_go_back,
        browser_get_url,
    ]
