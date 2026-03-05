"""Playwright browser lifecycle management for headed Edge sessions."""

import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright


AVAILABLE_BROWSERS = [
    {"id": "msedge", "name": "Microsoft Edge", "engine": "chromium", "channel": "msedge"},
    {"id": "chrome", "name": "Google Chrome", "engine": "chromium", "channel": "chrome"},
    {"id": "chromium", "name": "Chromium", "engine": "chromium", "channel": None},
    {"id": "firefox", "name": "Firefox", "engine": "firefox", "channel": None},
    {"id": "webkit", "name": "WebKit (Safari)", "engine": "webkit", "channel": None},
]


class BrowserController:
    """Manages a single headed browser session that the user can see and interact with."""

    def __init__(self, browser_id: str = "msedge"):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._browser_config = next(
            (b for b in AVAILABLE_BROWSERS if b["id"] == browser_id),
            AVAILABLE_BROWSERS[0],
        )

    @property
    def page(self) -> Page | None:
        return self._page

    @property
    def is_open(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    async def launch(self) -> Page:
        """Launch a visible browser window and return the active page."""
        if self.is_open:
            return self._page

        self._playwright = await async_playwright().start()
        engine = self._browser_config["engine"]
        channel = self._browser_config["channel"]
        launcher = getattr(self._playwright, engine)

        launch_kwargs = {"headless": False, "args": ["--start-maximized"]}
        if channel:
            launch_kwargs["channel"] = channel

        self._browser = await launcher.launch(**launch_kwargs)
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

    async def select_option(self, selector: str, value: str) -> str:
        """Select an option from a dropdown. Handles native <select> and custom dropdowns."""
        page = await self._ensure_page()

        # Strategy 1: Native <select> element
        try:
            is_select = await page.evaluate("""(sel) => {
                const el = document.querySelector(sel);
                return el && el.tagName === 'SELECT';
            }""", selector)

            if is_select:
                # Try by label first, then by value
                try:
                    await page.select_option(selector, label=value, timeout=5000)
                    return f"Selected '{value}' from native dropdown '{selector}'"
                except Exception:
                    await page.select_option(selector, value=value, timeout=5000)
                    return f"Selected '{value}' from native dropdown '{selector}'"
        except Exception:
            pass

        # Strategy 2: Custom dropdown — click to open, then find and click the option
        try:
            # Click the dropdown trigger to open it
            try:
                await page.click(selector, timeout=5000)
            except Exception:
                # Selector might be text — try to find and click it
                await page.get_by_text(selector, exact=False).first.click(timeout=5000)

            # Small delay for dropdown animation
            await page.wait_for_timeout(500)

            # Try to find the option by text and scroll it into view
            option = page.get_by_text(value, exact=False).first
            if await option.count() > 0:
                await option.scroll_into_view_if_needed(timeout=5000)
                await option.click(timeout=5000)
                return f"Selected '{value}' from custom dropdown '{selector}'"
        except Exception:
            pass

        # Strategy 3: For dropdowns with role="listbox" or role="option"
        try:
            await page.get_by_role("option", name=value).first.click(timeout=5000)
            return f"Selected '{value}' via ARIA option role"
        except Exception:
            pass

        # Strategy 4: Brute-force — find any visible element matching the value text after dropdown is open
        try:
            found = await page.evaluate("""(searchText) => {
                // Look for the option in common dropdown patterns
                const candidates = document.querySelectorAll(
                    '[role="option"], [role="listbox"] *, .dropdown-item, .option, ' +
                    'li, [class*="option"], [class*="menu-item"], [class*="select"] *'
                );
                for (const el of candidates) {
                    const text = (el.textContent || '').trim();
                    if (text === searchText || text.includes(searchText)) {
                        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        el.click();
                        return text;
                    }
                }
                // Fallback: walk all visible text
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    if (el.children.length === 0 || el.children.length === 1) {
                        const text = (el.textContent || '').trim();
                        if (text === searchText) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                el.click();
                                return text;
                            }
                        }
                    }
                }
                return null;
            }""", value)

            if found:
                return f"Selected '{found}' from dropdown via text search"
        except Exception:
            pass

        return f"Could not select '{value}' from '{selector}'. Try using browser_click with the exact option text instead."

    async def highlight(self, selector: str) -> str:
        """Highlight an element with a red border. Tries CSS selector first, then text search."""
        page = await self._ensure_page()

        # Try CSS selector first
        found = await page.evaluate("""(selector) => {
            const el = document.querySelector(selector);
            if (el && el.getBoundingClientRect().width > 0) {
                el.style.outline = '4px solid red';
                el.style.outlineOffset = '3px';
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return 'css';
            }
            return null;
        }""", selector)

        if found:
            return f"Highlighted element (CSS): {selector}"

        # Fallback: search by visible text content
        try:
            locator = page.get_by_text(selector, exact=False).first
            if await locator.count() > 0:
                await locator.evaluate("""(el) => {
                    // Walk up to find a meaningful container (not just a text node)
                    let target = el;
                    while (target.parentElement
                           && target.getBoundingClientRect().width < 50
                           && target.parentElement.tagName !== 'BODY') {
                        target = target.parentElement;
                    }
                    target.style.outline = '4px solid red';
                    target.style.outlineOffset = '3px';
                    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }""")
                return f"Highlighted element containing text: '{selector}'"
        except Exception:
            pass

        # Last resort: broad text search in the DOM
        found_text = await page.evaluate("""(searchText) => {
            const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (walk.nextNode()) {
                if (walk.currentNode.textContent.includes(searchText)) {
                    let el = walk.currentNode.parentElement;
                    // Walk up to a visible container
                    while (el && el.getBoundingClientRect().height < 10) {
                        el = el.parentElement;
                    }
                    if (el) {
                        el.style.outline = '4px solid red';
                        el.style.outlineOffset = '3px';
                        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        return el.textContent.substring(0, 100);
                    }
                }
            }
            return null;
        }""", selector)

        if found_text:
            return f"Highlighted element containing: '{found_text.strip()[:80]}'"

        return f"Could not find element matching '{selector}' on the page."

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
        """Close the browser and clean up. Safe to call multiple times."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass  # browser process may already be dead
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._context = None
        self._page = None

    async def _ensure_page(self) -> Page:
        if not self.is_open or not self._page:
            await self.launch()
        return self._page
