"""Playwright browser lifecycle management for headed browser sessions with persistent login."""

import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from rich.console import Console

# Use stderr so output doesn't interfere with MCP protocol on stdout
_console = Console(stderr=True)


AVAILABLE_BROWSERS = [
    {"id": "msedge", "name": "Microsoft Edge", "engine": "chromium", "channel": "msedge"},
    {"id": "chrome", "name": "Google Chrome", "engine": "chromium", "channel": "chrome"},
    {"id": "chromium", "name": "Chromium", "engine": "chromium", "channel": None},
    {"id": "firefox", "name": "Firefox", "engine": "firefox", "channel": None},
    {"id": "webkit", "name": "WebKit (Safari)", "engine": "webkit", "channel": None},
]

# Persistent profile directory — stores cookies, localStorage, and session data
# between runs so users don't have to re-login every time
PROFILE_DIR = Path(os.environ.get(
    "BROWSEPILOT_PROFILE_DIR",
    Path.home() / ".browsepilot" / "browser-profile",
))


class BrowserController:
    """Manages a single headed browser session that the user can see and interact with."""

    def __init__(self, browser_id: str = "msedge"):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._persistent = True  # use persistent context for login retention
        self._connected_via_cdp = False  # True when attached to an existing browser
        self._browser_config = next(
            (b for b in AVAILABLE_BROWSERS if b["id"] == browser_id),
            AVAILABLE_BROWSERS[0],
        )

    @property
    def page(self) -> Page | None:
        return self._page

    @property
    def is_open(self) -> bool:
        if self._persistent:
            return self._context is not None
        return self._browser is not None and self._browser.is_connected()

    async def launch(self) -> Page:
        """Launch a visible browser window with persistent profile and return the active page."""
        if self.is_open:
            return self._page

        browser_name = self._browser_config["name"]
        _console.print(f"[dim]🚀 Launching {browser_name}...[/]")

        self._playwright = await async_playwright().start()
        engine = self._browser_config["engine"]
        channel = self._browser_config["channel"]
        launcher = getattr(self._playwright, engine)

        # Ensure profile directory exists
        profile_dir = PROFILE_DIR / self._browser_config["id"]
        profile_dir.mkdir(parents=True, exist_ok=True)

        launch_kwargs = {
            "headless": False,
            "args": ["--start-maximized"],
            "no_viewport": True,
            "handle_sigint": False,  # Don't kill browser on Ctrl+C
            "handle_sigterm": False,  # Don't kill browser on SIGTERM
            "handle_sighup": False,  # Don't kill browser on SIGHUP
        }
        if channel:
            launch_kwargs["channel"] = channel

        # Use persistent context — retains cookies, localStorage, Entra ID SSO sessions
        self._context = await launcher.launch_persistent_context(
            user_data_dir=str(profile_dir),
            **launch_kwargs,
        )
        # Persistent context may open with multiple restored tabs — use the first, close extras
        if self._context.pages:
            self._page = self._context.pages[0]
            # Close any extra tabs that were restored from the profile
            for extra_page in self._context.pages[1:]:
                try:
                    await extra_page.close()
                except Exception:
                    pass
        else:
            self._page = await self._context.new_page()

        _console.print(f"[dim]✓ {browser_name} is ready (profile: {profile_dir.name})[/]")
        return self._page

    async def connect_cdp(self, endpoint: str = "http://localhost:9222") -> str:
        """Connect to an already-running Chromium/Edge/Chrome browser via CDP.

        The target browser must have been started with
        --remote-debugging-port=9222 (or whichever port ``endpoint`` points to).

        Returns a summary of open tabs.
        """
        # Tear down any previous session first.
        await self.close()

        self._playwright = await async_playwright().start()
        _console.print(f"[dim]🔗 Connecting to browser at {endpoint}...[/]")
        self._browser = await self._playwright.chromium.connect_over_cdp(endpoint)
        self._connected_via_cdp = True
        self._persistent = False  # CDP mode is not a persistent context

        # Pick the first context (the default profile) and the active page.
        contexts = self._browser.contexts
        if not contexts:
            raise RuntimeError("Connected via CDP but found no browser contexts.")
        self._context = contexts[0]
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        tab_summary = await self.list_pages()
        _console.print(f"[dim]✓ Connected to existing browser ({len(self._context.pages)} tab(s))[/]")
        return tab_summary

    async def list_pages(self) -> str:
        """Return a numbered list of all open tabs in the attached browser."""
        if not self._context:
            return "No browser connected. Use connect_cdp() or launch() first."
        lines = ["Open tabs:"]
        for i, pg in enumerate(self._context.pages):
            try:
                title = await pg.title()
            except Exception:
                title = "(unknown)"
            marker = "  →" if pg == self._page else "   "
            lines.append(f"{marker} [{i}] {title}  ({pg.url})")
        return "\n".join(lines)

    async def switch_to_page(self, tab_index: int | None = None, url_substring: str | None = None) -> str:
        """Switch to a different tab by index or by URL substring."""
        if not self._context:
            return "No browser connected."
        pages = self._context.pages
        if not pages:
            return "No tabs open."

        target: Page | None = None
        if tab_index is not None:
            if 0 <= tab_index < len(pages):
                target = pages[tab_index]
            else:
                return f"Invalid tab index {tab_index}. There are {len(pages)} tab(s) (0-{len(pages)-1})."
        elif url_substring is not None:
            for pg in pages:
                if url_substring.lower() in pg.url.lower():
                    target = pg
                    break
            if target is None:
                return f"No tab found whose URL contains '{url_substring}'."
        else:
            return "Provide either tab_index or url_substring."

        self._page = target
        await target.bring_to_front()
        try:
            title = await target.title()
        except Exception:
            title = "(unknown)"
        return f"Switched to tab [{pages.index(target)}]: {title} ({target.url})"

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> str:
        """Navigate to a URL and return the page title."""
        page = await self._ensure_page()

        # First try a straightforward navigation. If the underlying browser was
        # killed or the target/page was closed, attempt a one-time reconnect
        # instead of surfacing a low-level Playwright error to the caller.
        try:
            await page.goto(url, wait_until=wait_until, timeout=30000)
        except Exception as e:
            message = str(e)
            if any(token in message for token in [
                "Target closed",
                "has been closed",
                "browser has disconnected",
            ]):
                _console.print("[dim]🔄 Browser was closed; relaunching and retrying navigation...[/]")
                await self.close()
                page = await self.launch()
                await page.goto(url, wait_until=wait_until, timeout=30000)
            else:
                raise

        # Reading the title immediately after heavy SPA navigations (like Azure
        # Portal) can sometimes hit "Execution context was destroyed" while the
        # page is still settling. Handle that gracefully with a short wait and
        # a single retry instead of treating it as a fatal error.
        try:
            return await page.title()
        except Exception as e:
            message = str(e)
            if "Execution context was destroyed" in message:
                _console.print("[dim]ℹ Page is still navigating; waiting before reading title...[/]")
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    return await page.title()
                except Exception:
                    # Fall back to the URL if title remains unavailable.
                    return page.url
            raise

    async def get_page_content(self, max_length: int = 15000) -> str:
        """Extract readable text content from the current page."""
        page = await self._ensure_page()
        extract_script = """() => {
            // Remove scripts, styles, and hidden elements
            const clone = document.body.cloneNode(true);
            clone.querySelectorAll('script, style, noscript, [aria-hidden="true"]').forEach(el => el.remove());
            return clone.innerText.substring(0, """ + str(max_length) + """);
        }"""

        # Be resilient to transient navigations while we read the DOM.
        try:
            content = await page.evaluate(extract_script)
        except Exception as e:
            message = str(e)
            if "Execution context was destroyed" in message:
                _console.print("[dim]ℹ Page reload detected while reading content; retrying after load...[/]")
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    content = await page.evaluate(extract_script)
                except Exception:
                    content = ""
            else:
                raise

        try:
            title = await page.title()
        except Exception:
            title = ""

        try:
            url = page.url
        except Exception:
            url = ""
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

    async def screenshot(self, path: str = "") -> str:
        """Take a screenshot of the current page and open it for the user."""
        import time
        import subprocess
        page = await self._ensure_page()

        if not path:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            screenshots_dir = Path.home() / ".browsepilot" / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            path = str(screenshots_dir / f"screenshot_{timestamp}.png")

        await page.screenshot(path=path, full_page=False)
        title = await page.title()
        url = page.url

        # Auto-open the screenshot for the user
        try:
            if os.name == "nt":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

        return f"Screenshot saved and opened: {path}\nPage: {title}\nURL: {url}"

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
        if self._connected_via_cdp:
            # When connected via CDP we don't own the browser — just disconnect.
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            self._context = None
        else:
            if self._context:
                try:
                    await self._context.close()
                except Exception:
                    pass
                self._context = None
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
        self._page = None
        self._connected_via_cdp = False

    async def _ensure_page(self) -> Page:
        """Ensure we have a live browser page. Re-launch if connection was lost."""
        # Avoid expensive or fragile health checks on every call. Prefer cheap
        # structural checks and only relaunch when it is clear the page is
        # gone, which keeps MCP tool calls fast and reduces spurious
        # reconnects while a page is simply mid-navigation.
        if self.is_open and self._page and not self._page.is_closed():
            return self._page

        if not self.is_open:
            # Clean up any stale handles so a fresh launch starts from a
            # consistent state.
            await self.close()

        _console.print("[dim]🔄 (Re)launching browser page...[/]")
        await self.launch()
        return self._page
