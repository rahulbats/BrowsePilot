"""BrowsePilot - AI-powered browser co-pilot using GitHub Copilot SDK + Playwright."""

import asyncio
import atexit
import signal
import sys
from copilot import CopilotClient, PermissionHandler
from rich.console import Console
from rich.markdown import Markdown
from browser import create_browser_tools, get_browser, init_browser, AVAILABLE_BROWSERS

console = Console()

SYSTEM_PROMPT = """You are BrowsePilot, an AI assistant that helps users navigate and understand web portals and websites using a REAL browser.

## Your Key Capability
You have access to browser tools that control a real, visible Microsoft Edge window on the user's screen. Unlike other AI assistants, you can SEE what's actually on a webpage right now — not rely on potentially outdated training data.

## When to Use Browser Tools
- When a user asks how to do something on a website (Azure Portal, AWS Console, GitHub, etc.)
- When a user needs step-by-step guidance through a web UI
- When you need to verify current UI layout, button names, or menu structures
- When your training data might be outdated about a website's interface

## How to Help
1. **Navigate first**: Use `browser_navigate` to open the relevant page
2. **Read the page**: Use `browser_read_page` to see what's actually there
3. **List elements**: Use `browser_list_elements` to find buttons, links, and inputs
4. **Guide visually**: Use `browser_highlight` to point out elements with a red border
5. **Act when asked**: Use `browser_click` or `browser_fill` to perform actions the user requests

## Important Rules
- ALWAYS read the actual page content before giving instructions — never guess from memory
- Tell the user what you see on the page, referencing actual button text and menu names
- If a page requires login, tell the user to log in manually in the browser window — you'll wait
- When highlighting elements, describe where they are so the user can find them
- Be concise and action-oriented: "Click the blue 'Create' button in the top-left" not "You might want to look for a button"

## Response Style
- Use short, clear steps
- Reference exact UI text you see on the page (in quotes)
- Proactively highlight relevant elements for the user
"""


async def handle_user_input(request, invocation):
    """Handle ask_user requests from the agent."""
    question = request.get("question", "")
    choices = request.get("choices", [])

    console.print(f"\n[bold yellow]Agent asks:[/] {question}")
    if choices:
        for i, choice in enumerate(choices):
            console.print(f"  [{i + 1}] {choice}")

    answer = input("> ").strip()
    return {"answer": answer, "wasFreeform": True}


async def pick_model(client) -> str:
    """Fetch available models and let the user pick one."""
    console.print("\n[bold cyan]Fetching available models...[/]")
    try:
        models = await client.list_models()
    except Exception as e:
        console.print(f"[yellow]Could not fetch models ({e}). Defaulting to gpt-4o.[/]")
        return "gpt-4o"

    if not models:
        console.print("[yellow]No models returned. Defaulting to gpt-4o.[/]")
        return "gpt-4o"

    console.print("[bold cyan]Available Models:[/]")
    for i, model in enumerate(models):
        billing = ""
        if model.billing:
            billing = f" — [dim]{model.billing}[/]"
        console.print(f"  [green][{i + 1}][/] {model.name} [dim]({model.id})[/]{billing}")

    while True:
        try:
            choice = input(f"\nSelect model [1-{len(models)}] (default: 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            return models[0].id
        if not choice:
            return models[0].id
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            selected = models[int(choice) - 1]
            console.print(f"[green]✓ Using model:[/] {selected.name}")
            return selected.id
        console.print("[red]Invalid choice. Try again.[/]")


def pick_browser() -> str:
    """Let the user pick a browser from the available list."""
    console.print("\n[bold cyan]Available Browsers:[/]")
    for i, b in enumerate(AVAILABLE_BROWSERS):
        default_tag = " [dim](default)[/]" if i == 0 else ""
        console.print(f"  [green][{i + 1}][/] {b['name']}{default_tag}")

    while True:
        try:
            choice = input(f"\nSelect browser [1-{len(AVAILABLE_BROWSERS)}] (default: 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            return AVAILABLE_BROWSERS[0]["id"]
        if not choice:
            selected = AVAILABLE_BROWSERS[0]
            console.print(f"[green]✓ Using browser:[/] {selected['name']}")
            return selected["id"]
        if choice.isdigit() and 1 <= int(choice) <= len(AVAILABLE_BROWSERS):
            selected = AVAILABLE_BROWSERS[int(choice) - 1]
            console.print(f"[green]✓ Using browser:[/] {selected['name']}")
            return selected["id"]
        console.print("[red]Invalid choice. Try again.[/]")


async def main():
    console.print("[bold green]🌐 BrowsePilot[/] — AI-powered browser co-pilot")
    console.print("[dim]Type your question about any website or web portal. Type 'quit' to exit.[/]")

    client = CopilotClient()
    await client.start()

    # --- Selection phase ---
    model_id = await pick_model(client)
    browser_id = pick_browser()
    console.print()

    browser = init_browser(browser_id)
    browser_tools = create_browser_tools()

    session = await client.create_session({
        "model": model_id,
        "streaming": True,
        "tools": browser_tools,
        "system_message": {"content": SYSTEM_PROMPT},
        "on_user_input_request": handle_user_input,
        "on_permission_request": PermissionHandler.approve_all,
    })

    try:
        while True:
            try:
                user_input = input("\n🧑 You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                break

            done = asyncio.Event()
            streamed = False

            def on_event(event):
                nonlocal streamed
                event_type = event.type.value if hasattr(event.type, "value") else str(event.type)

                if event_type == "assistant.message_delta":
                    delta = event.data.delta_content or ""
                    print(delta, end="", flush=True)
                    streamed = True
                elif event_type == "assistant.message":
                    if streamed:
                        print()  # newline after streaming
                    else:
                        console.print(event.data.content)
                elif event_type == "tool.executing":
                    tool_name = getattr(event.data, "name", "unknown")
                    console.print(f"[dim]⚙️  Using tool: {tool_name}...[/]")
                elif event_type == "session.idle":
                    done.set()

            unsubscribe = session.on(on_event)
            console.print("[bold blue]🤖 BrowsePilot:[/] ", end="")
            await session.send({"prompt": user_input})
            await done.wait()
            unsubscribe()

    finally:
        await cleanup(browser, session, client)


async def cleanup(browser=None, session=None, client=None):
    """Gracefully shut down all resources. Each step is independent so one failure won't block the rest."""
    console.print("\n[dim]Closing browser and cleaning up...[/]")

    if browser:
        try:
            await asyncio.wait_for(browser.close(), timeout=5.0)
        except Exception as e:
            console.print(f"[dim yellow]Browser close: {e}[/]")

    if session:
        try:
            await asyncio.wait_for(session.destroy(), timeout=5.0)
        except Exception as e:
            console.print(f"[dim yellow]Session destroy: {e}[/]")

    if client:
        try:
            await asyncio.wait_for(client.stop(), timeout=5.0)
        except Exception as e:
            console.print(f"[dim yellow]Client stop: {e}[/]")

    # Force-kill any lingering Playwright browser processes
    _kill_playwright_processes()

    console.print("[bold green]Goodbye![/]")


def _kill_playwright_processes():
    """Kill any leftover msedge/chromium/firefox processes spawned by Playwright."""
    try:
        import subprocess
        # Playwright spawns browsers with --remote-debugging-pipe; target those specifically
        if sys.platform == "win32":
            for proc_name in ["msedge.exe", "chromium.exe", "firefox.exe", "chrome.exe"]:
                subprocess.run(
                    ["taskkill", "/F", "/FI", f"IMAGENAME eq {proc_name}", "/FI", "WINDOWTITLE eq *Playwright*"],
                    capture_output=True, timeout=3,
                )
    except Exception:
        pass  # best-effort


if __name__ == "__main__":
    # Handle Ctrl+C gracefully on Windows
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[dim]Interrupted — forcing cleanup...[/]")
        _kill_playwright_processes()
    finally:
        # Last-resort atexit isn't needed, but just in case
        pass
