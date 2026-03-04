"""CopilotBrowsePilot - AI-powered browser co-pilot using GitHub Copilot SDK + Playwright."""

import asyncio
import sys
from copilot import CopilotClient
from rich.console import Console
from rich.markdown import Markdown
from browser import create_browser_tools, get_browser

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


async def main():
    console.print("[bold green]🌐 CopilotBrowsePilot[/] — AI-powered browser co-pilot")
    console.print("[dim]Type your question about any website or web portal. Type 'quit' to exit.[/]\n")

    client = CopilotClient()
    await client.start()

    browser_tools = create_browser_tools()
    browser = get_browser()

    session = await client.create_session({
        "model": "gpt-5",
        "streaming": True,
        "tools": browser_tools,
        "system_message": {"content": SYSTEM_PROMPT},
        "on_user_input_request": handle_user_input,
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
            full_response = []

            def on_event(event):
                event_type = event.type.value if hasattr(event.type, "value") else str(event.type)

                if event_type == "assistant.message_delta":
                    delta = event.data.delta_content or ""
                    print(delta, end="", flush=True)
                    full_response.append(delta)
                elif event_type == "assistant.message":
                    if not full_response:
                        # Non-streaming fallback
                        console.print(f"\n[bold blue]🤖 BrowsePilot:[/] {event.data.content}")
                    else:
                        print()  # newline after streaming
                elif event_type == "tool.executing":
                    tool_name = getattr(event.data, "name", "unknown")
                    console.print(f"\n[dim]⚙️  Using tool: {tool_name}...[/]", end="")
                elif event_type == "session.idle":
                    done.set()

            session.on(on_event)
            console.print("[bold blue]🤖 BrowsePilot:[/] ", end="")
            await session.send({"prompt": user_input})
            await done.wait()

    finally:
        console.print("\n[dim]Closing browser and cleaning up...[/]")
        await browser.close()
        await session.destroy()
        await client.stop()
        console.print("[bold green]Goodbye![/]")


if __name__ == "__main__":
    asyncio.run(main())
