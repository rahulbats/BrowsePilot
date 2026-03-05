# 🌐 BrowsePilot

**AI that browses with you, not for you.** Built with the GitHub Copilot SDK.

## The Problem

Every day, enterprise users ask AI assistants questions like:

> *"How do I create a resource group in Azure Portal?"*
> *"Where do I assign licenses in M365 Admin Center?"*
> *"How do I enable branch protection on GitHub?"*

The AI confidently gives step-by-step instructions — referencing buttons, menus, and layouts that **no longer exist**. The UI changed after the training cutoff. The user follows phantom instructions, gets lost, and **loses trust in AI assistance**.

This is not a minor inconvenience. In enterprise environments:
- **IT helpdesks** waste cycles on portal navigation questions
- **New hires** struggle with unfamiliar admin portals
- **Support teams** give outdated guidance because even docs lag behind UI changes

## The Solution

**BrowsePilot** is like having someone look over your shoulder and point at the screen:

```
🧑 You: How do I create a new resource group in Azure Portal?

🤖 BrowsePilot: Let me open Azure Portal and check the current UI...
   ⚙️  browser_navigate → portal.azure.com
   ⚙️  browser_read_page
   ⚙️  browser_highlight → "Resource groups"

   I can see the Azure Portal. Here are the exact steps:
   1. Click "Resource groups" in the left sidebar (I've highlighted it in red)
   2. Click the "+ Create" button in the top toolbar
   3. Fill in your subscription, resource group name, and region
   4. Click "Review + create"
```

The user sees a **real browser window** open on their screen with elements highlighted — grounded, trustworthy guidance powered by the GitHub Copilot SDK.

## Why This Is Different

Existing AI browser agents (Browser-Use, Anthropic Computer Use, LaVague) are **autonomous** — you give them a task and they do everything with no visibility. BrowsePilot is a **co-pilot**:

| | Autonomous Agents | CopilotBrowsePilot |
|---|---|---|
| **User involvement** | None — black box | User watches every step |
| **Credentials** | Needs stored API keys/tokens | User logs in themselves — zero exposure |
| **Trust model** | "Trust the AI did it right" | User sees and verifies every action |
| **Enterprise readiness** | Risky for production portals | Safe — user confirms before sensitive actions |
| **Cost** | Separate LLM API costs | Uses existing Copilot subscription |
| **Learning** | User learns nothing | User learns the actual workflow |

> **Other browser agents replace the user. BrowsePilot works alongside them.**


## Enterprise Value

### For IT Helpdesks
Reduce Tier 1 portal navigation tickets by enabling users to self-serve with real-time, visually guided instructions.

### For Onboarding
New hires get a personal guide through any admin portal — Azure, M365, GitHub Enterprise, ServiceNow — without scheduling a shadow session.

### For Support Engineers
Instead of writing "click the button that says X" in docs (which goes stale), point users to BrowsePilot. It reads the **current** UI every time.

### Reusable Pattern
The browser tools are generic. Swap the system prompt for any domain:
- **Azure Portal** — Resource management, IAM, deployments
- **M365 Admin Center** — User management, license assignment
- **GitHub Enterprise** — Repository settings, org management
- **Salesforce / ServiceNow / Dynamics 365** — Any web-based enterprise tool
- **Internal web apps** — Custom portals with no public documentation

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                      User                            │
│        Asks a question in the terminal               │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│            GitHub Copilot SDK Session                 │
│     (Model auto-selected from available models)      │
│                                                      │
│  Browser Tools (Playwright):                         │
│   🔗 browser_navigate     Navigate to any URL        │
│   📖 browser_read_page    Extract live page content  │
│   🔍 browser_list_elements Find buttons, links, etc. │
│   👆 browser_click        Click elements by text/CSS │
│   ✏️  browser_fill         Fill form fields           │
│   📋 browser_select       Select from dropdowns      │
│   🔴 browser_highlight    Highlight with red border  │
│   📸 browser_screenshot   Capture page state         │
│   ⬅️  browser_go_back      Navigate back              │
│   🔗 browser_get_url      Get current URL            │
└────────────────┬────────────────────────────────────┘
                 │ Playwright
                 ▼
┌─────────────────────────────────────────────────────┐
│          Real Browser Window (user's screen)         │
│                                                      │
│   • Headed mode — user sees every action             │
│   • Supports Edge, Chrome, Chromium, Firefox, WebKit │
│   • User can interact alongside the agent            │
│   • AI reads real DOM — no hallucinations            │
└─────────────────────────────────────────────────────┘
```

## Features

### Dynamic Model Selection
On startup, the app queries available Copilot SDK models and lets the user choose:
```
Available Models:
  [1] GPT-4o (gpt-4o)
  [2] GPT-5 (gpt-5) — premium
  [3] Claude Sonnet (claude-sonnet-4) — premium

Select model [1-3]: 2
✓ Using model: GPT-5
```

### Multi-Browser Support
Choose from any Playwright-supported browser:
```
Available Browsers:
  [1] Microsoft Edge (default)
  [2] Google Chrome
  [3] Chromium
  [4] Firefox
  [5] WebKit (Safari)

Select browser [1-5]: 1
✓ Using browser: Microsoft Edge
```

### Smart Element Highlighting
The highlight tool uses a 3-tier fallback for complex SPAs like Azure Portal:
1. **CSS selector** — fast, exact match
2. **Text-based search** — finds elements by visible text content
3. **DOM TreeWalker** — brute-force scan for deeply nested elements

Pass visible text like `"$150.00 credits remaining"` instead of guessing CSS selectors.

### Intelligent Dropdown Selection
Handles both native `<select>` elements and custom JavaScript dropdowns:
- Native HTML selects via `select_option()`
- Custom dropdowns: click to open → scroll into view → click option
- ARIA role-based matching (`role="option"`)
- Brute-force DOM pattern matching for non-standard dropdowns

### Robust Cleanup
- Each cleanup step (browser, session, client) is independent with 5-second timeouts
- Force-kills lingering Playwright processes on exit
- Ctrl+C is handled gracefully on Windows — no zombie processes

## Setup

### Prerequisites

- Python 3.11+
- GitHub Copilot CLI installed and authenticated (`gh auth login`)
- A browser (Edge is default; Chrome, Firefox also supported)

### Installation

```bash
# Clone the repo
git clone https://github.com/your-username/copilot-browse-pilot.git
cd copilot-browse-pilot

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser(s)
playwright install msedge        # or: playwright install chromium
```

### Run

```bash
python main.py
```

Select your model and browser, then start asking questions about any website.

## Demo Scenarios

### 1. Azure Portal — Create a Resource Group
```
You: How do I create a new resource group in Azure Portal?
→ Opens Edge, navigates to portal.azure.com
→ Reads the live UI, highlights "Resource groups" in the sidebar
→ Walks through each step with exact button names from the current UI
```

### 2. GitHub — Enable Branch Protection
```
You: How do I enable branch protection rules on my repo?
→ Navigates to repo Settings → Branches
→ Lists actual available options, highlights "Add branch protection rule"
→ Guides through the form fields
```

### 3. Form Filling — State Dropdown
```
You: Fill in Texas as the state in this form
→ Finds the state dropdown, clicks to open it
→ Scrolls down to "Texas", selects it
→ Confirms the selection
```

### 4. Verifying Outdated Instructions
```
You: The docs say to click "All Services" in Azure Portal. Is that still there?
→ Opens Azure Portal, reads the actual page
→ Reports whether "All Services" exists or what replaced it
```

## Project Structure

```
copilot-browse-pilot/
├── main.py                 # Entry point — model/browser picker + chat loop
├── requirements.txt        # Python dependencies
├── README.md
└── browser/
    ├── __init__.py         # Package exports
    ├── controller.py       # Playwright browser lifecycle + all browser actions
    └── tools.py            # @define_tool definitions for Copilot SDK
```

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| **Agent Runtime** | [GitHub Copilot SDK](https://github.com/github/copilot-sdk) | Challenge requirement; enterprise auth built-in |
| **Browser Control** | [Playwright](https://playwright.dev/python/) | Microsoft-built; supports Edge, Chrome, Firefox, WebKit |
| **Terminal UI** | [Rich](https://github.com/Textualize/rich) | Clean formatting for the chat interface |
| **Default Browser** | Microsoft Edge | Enterprise default across MCAPS |

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **Headed browser only** | The visible browser IS the feature — users see exactly what AI sees |
| **No credential handling** | User logs in manually — zero security risk, full enterprise trust |
| **DOM-grounded responses** | Agent must read the page before answering — never guesses from memory |
| **Visual highlighting** | Red borders + auto-scroll guide users to exact elements |
| **Text-based highlight** | CSS selectors fail on complex SPAs; text matching is more reliable |
| **Multi-browser** | Enterprises use different browsers; don't assume Edge |
| **Dynamic model selection** | Let users choose the best model for their task and budget |

## Future Directions

- **Custom agents** — Split into specialist agents (navigator, form filler, visual guide) using Copilot SDK's `custom_agents` for better tool routing
- **Session transcript logging** — Save conversations + tool calls for audit trails
- **Multi-tab support** — Compare information across multiple pages
- **Screenshot analysis** — Send screenshots to vision models for richer page understanding
- **VS Code Chat Participant** — Port to a `@browsepilot` chat participant for seamless IDE integration

## License

MIT
