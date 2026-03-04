# 🌐 CopilotBrowsePilot

**AI that browses with you, not for you.** A GitHub Copilot SDK agent with real browser superpowers.

> Built for the FY26 GitHub Copilot SDK Enterprise Challenge

## The Problem

AI assistants frequently give **wrong or outdated instructions** for web portals. Ask any AI "How do I create a resource group in Azure Portal?" and you'll likely get steps referencing buttons and menus that **no longer exist** — because the UI changed after the training cutoff.

**This erodes trust.** Enterprise users waste time following phantom instructions, then lose confidence in AI assistance altogether.

## The Solution

**CopilotBrowsePilot** is a GitHub Copilot SDK-powered agent that can **open a real browser window** and read what's actually on the screen. Instead of hallucinating UI elements, it navigates to the real page, reads the live DOM, and guides you step-by-step based on **what's actually there**.

```
🧑 You: How do I create a new resource group in Azure Portal?

🤖 BrowsePilot: Let me open Azure Portal and check the current UI...
   ⚙️ Using tool: browser_navigate...
   ⚙️ Using tool: browser_read_page...
   ⚙️ Using tool: browser_highlight...

   I can see the Azure Portal. Here are the exact steps:
   1. Click "Resource groups" in the left sidebar (I've highlighted it in red)
   2. Click the "+ Create" button in the top toolbar
   3. Fill in your subscription, resource group name, and region
   4. Click "Review + create"
```

The user sees a **real Edge browser window** open on their screen with elements highlighted — grounded, trustworthy guidance.

## Architecture

```
┌──────────────────────────────────────────────┐
│                   User                        │
│              (types in CLI)                   │
└──────────┬───────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│          Copilot SDK Session                  │
│    (GPT-5 with custom browser tools)          │
│                                               │
│  Tools:                                       │
│   🔗 browser_navigate    - Go to URL          │
│   📖 browser_read_page   - Read DOM content   │
│   🔍 browser_list_elements - Find UI elements │
│   👆 browser_click       - Click elements     │
│   ✏️  browser_fill        - Fill form fields   │
│   🔴 browser_highlight   - Highlight elements │
│   📸 browser_screenshot  - Capture page       │
│   ⬅️  browser_go_back     - Navigate back      │
└──────────┬───────────────────────────────────┘
           │ Playwright
           ▼
┌──────────────────────────────────────────────┐
│         Real Microsoft Edge Window            │
│     (visible on user's screen)                │
│                                               │
│   User can see AND interact with the browser  │
│   AI reads real DOM — no hallucinations       │
└──────────────────────────────────────────────┘
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **Headed browser only** | The visible browser IS the feature — users see exactly what AI sees |
| **No credential handling** | User logs in manually — zero security risk, full trust |
| **DOM-grounded responses** | Agent MUST read the page before answering — no guessing |
| **Visual highlighting** | Red borders + auto-scroll guide users to exact elements |
| **Microsoft Edge** | Enterprise default browser — great optics for MCAPS |

## Reusable Enterprise Pattern

This pattern applies to **any enterprise web portal**:

- **Azure Portal** — Resource management, IAM, deployments
- **M365 Admin Center** — User management, license assignment
- **GitHub Enterprise** — Repository settings, org management
- **Salesforce** — CRM workflows, report building
- **ServiceNow** — Ticket management, catalog requests
- **Any internal enterprise web app**

The browser tools are generic — swap the system prompt for any domain.

## Setup

### Prerequisites

- Python 3.11+
- [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli) installed and authenticated
- Microsoft Edge browser

### Installation

```bash
# Clone the repo
git clone https://github.com/your-username/copilot-browse-pilot.git
cd copilot-browse-pilot

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install msedge
```

### Run

```bash
python main.py
```

A chat interface starts. Ask any question about a website — the agent will open Edge and guide you through it.

## Demo Scenarios

### 1. Azure Portal: Create a Resource Group
```
You: How do I create a new resource group in Azure Portal?
→ Agent opens Edge, navigates to portal.azure.com, reads the real UI, highlights elements
```

### 2. GitHub: Enable Branch Protection
```
You: How do I enable branch protection rules on my GitHub repo?
→ Agent navigates to repo settings, reads actual options, guides step-by-step
```

### 3. Verifying Outdated Instructions
```
You: The docs say to click "All Services" in Azure Portal. Is that still correct?
→ Agent opens Azure Portal, checks if "All Services" exists, reports what's actually there
```

## Project Structure

```
copilot-browse-pilot/
├── main.py                 # Entry point — interactive chat with Copilot SDK
├── requirements.txt        # Python dependencies
├── browser/
│   ├── __init__.py
│   ├── controller.py       # Playwright browser lifecycle (open/close/navigate)
│   └── tools.py            # @define_tool definitions for Copilot SDK
├── .env.example
├── .gitignore
└── README.md
```

## Tech Stack

- **[GitHub Copilot SDK](https://github.com/github/copilot-sdk)** — Agent runtime with custom tool support
- **[Playwright](https://playwright.dev/python/)** — Browser automation (Microsoft)
- **[Rich](https://github.com/Textualize/rich)** — Terminal formatting
- **Microsoft Edge** — Enterprise browser

## License

MIT
