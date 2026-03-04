"""Playwright browser lifecycle management for headed Edge sessions."""

import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright


class BrowserController:
    """Manages a single headed Edge browser session that the user can see and interact with."""

    def __init__(self):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page | None:
        return self._page

    @property
    def is_open(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    async def launch(self) -> Page:
        """Launch a visible Edge browser window and return the active page."""
        if self.is_open:
            return self._page

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False,
            channel="msedge",
            args=["--start-maximized"],
        )
        self._context = await self._browser.new_context(
            no_viewport=True,  # use full window size
        )
        self._page = await self._context.new_page()
        return self._page

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> str:
        """Navigate to a URL and return the page title."""
        page = await self._ensure_page()
        await page.goto(url, wait_until=wait_until, timeout=30000)
        return await page.title()

    async def get_page_content(self, max_length: int = 15000) -> str:
        """Extract readable text content from the current page."""
        page = await self._ensure_page()
        content = await page.evaluate("""() => {
            // Remove scripts, styles, and hidden elements
            const clone = document.body.cloneNode(true);
            clone.querySelectorAll('script, style, noscript, [aria-hidden="true"]').forEach(el => el.remove());
            return clone.innerText.substring(0, """ + str(max_length) + """);
        }""")
        title = await page.title()
        url = page.url
        return f"Page: {title}\nURL: {url}\n\n{content}"

    async def get_interactive_elements(self) -> str:
        """List all interactive elements (buttons, links, inputs) on the page."""
        page = await self._ensure_page()
        elements = await page.evaluate("""() => {
            const results = [];
            const selectors = 'a, button, input, select, textarea, [role="button"], [role="link"], [role="tab"], [role="menuitem"]';
            document.querySelectorAll(selectors).forEach((el, i) => {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return; // skip hidden
                const text = (el.textContent || '').trim().substring(0, 80);
                const tag = el.tagName.toLowerCase();
                const type = el.getAttribute('type') || '';
                const ariaLabel = el.getAttribute('aria-label') || '';
                const placeholder = el.getAttribute('placeholder') || '';
                const label = text || ariaLabel || placeholder || `[${tag}${type ? ':' + type : ''}]`;
                results.push({
                    index: i,
                    tag: tag,
                    type: type,
                    label: label,
                    selector: el.id ? `#${el.id}` : null,
                });
            });
            return results.slice(0, 50); // cap at 50 elements
        }""")
        if not elements:
            return "No interactive elements found on this page."
        lines = ["Interactive elements on this page:"]
        for el in elements:
            selector_hint = f' (selector: {el["selector"]})' if el.get("selector") else ""
            lines.append(f'  [{el["index"]}] <{el["tag"]}> {el["label"]}{selector_hint}')
        return "\n".join(lines)

    async def click(self, selector: str) -> str:
        """Click an element by CSS selector or text content."""
        page = await self._ensure_page()
        try:
            await page.click(selector, timeout=5000)
        except Exception:
            # Try by text
            await page.get_by_text(selector, exact=False).first.click(timeout=5000)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        return f"Clicked '{selector}'. Page is now: {await page.title()} ({page.url})"

    async def fill(self, selector: str, value: str) -> str:
        """Fill a form field with a value."""
        page = await self._ensure_page()
        await page.fill(selector, value, timeout=5000)
        return f"Filled '{selector}' with '{value}'"

    async def highlight(self, selector: str) -> str:
        """Highlight an element with a red border to visually guide the user."""
        page = await self._ensure_page()
        await page.evaluate(f"""(selector) => {{
            const el = document.querySelector(selector);
            if (el) {{
                el.style.outline = '3px solid red';
                el.style.outlineOffset = '2px';
                el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
        }}""", selector)
        return f"Highlighted element: {selector}"

    async def screenshot(self, path: str = "screenshot.png") -> str:
        """Take a screenshot of the current page."""
        page = await self._ensure_page()
        await page.screenshot(path=path, full_page=False)
        return f"Screenshot saved to {path}"

    async def get_url(self) -> str:
        """Get the current page URL."""
        page = await self._ensure_page()
        return page.url

    async def go_back(self) -> str:
        """Navigate back in browser history."""
        page = await self._ensure_page()
        await page.go_back(wait_until="domcontentloaded", timeout=10000)
        return f"Navigated back to: {await page.title()} ({page.url})"

    async def close(self):
        """Close the browser and clean up."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._context = None
        self._page = None

    async def _ensure_page(self) -> Page:
        if not self.is_open or not self._page:
            await self.launch()
        return self._page
