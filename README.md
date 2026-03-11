<div align="center">

```
 ██████╗ ███████╗███╗   ██╗ ██████╗
██╔════╝ ██╔════╝████╗  ██║██╔════╝
██║  ███╗█████╗  ██╔██╗ ██║███████╗
██║   ██║██╔══╝  ██║╚██╗██║██═══██║
╚██████╔╝███████╗██║ ╚████║███████║
 ╚═════╝ ╚══════╝╚═╝  ╚═══╝╚══════╝
```

# Gen6

### **AI-Powered B2B Lead Generation & Sales Intelligence Platform**

*Built by TARS Technologies*

---


</div>

---

## What is Gen6?

**Gen6** is a full-stack B2B sales intelligence platform that automates the hardest parts of early-stage sales: finding the right companies, qualifying them, and reaching out — all supercharged by AI.

Instead of spending hours manually searching Google, hunting for emails, and writing cold outreach templates, Gen6 does it all in one place:

- Tell it what you're building
- It suggests which industries to target
- It finds real companies via Google Maps
- It qualifies them with AI
- It writes personalized cold emails
- It sends them — directly from the platform

Built for **startup founders, B2B sales teams, and solo operators** who need to move fast.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Module Reference](#module-reference)
- [API Routes](#api-routes)
- [Screenshots & Pages](#screenshots--pages)
- [Security](#security)
- [Known Limitations](#known-limitations)

---

## Features

### 🤖 AI-Powered Intelligence
- **Industry Suggestion Engine** — describe your product and the AI instantly suggests the best industries to target
- **Lead Relevance Filter** — AI reads your project description and scores company leads for relevance
- **Cross-Project Matching** — discovers which companies match *multiple* projects, surfacing upsell opportunities
- **Industry Portfolio Analysis** — see which companies in your pipeline are the best fit across all your products
- **AI Sales Advisor Chat** — a contextual chatbot that knows your product and advises on sales strategy

### 🏢 Company Discovery & Enrichment
- **Google Maps Search** (via SerpAPI) — finds real local businesses by industry and city
- **Website Scraping** — extracts email addresses and descriptions from company websites automatically
- **CEO LinkedIn Lookup** — finds the CEO's name and LinkedIn profile URL
- **Company & Leadership LinkedIn** — discovers both the company page and a leadership profile on LinkedIn

### 🗂️ Multi-Project Workspace
- Create unlimited projects, each with its own name, description, logo, and lead pipeline
- Switch between projects from any page — each has its own isolated company database
- Upload custom logos for each project

### 📋 Lead Qualification Pipeline
Every lead goes through a 3-stage funnel:
```
🔍 More To Explore  →  📞 Call For Action  →  ❌ Declined
```
Qualify leads by clicking company cards in the Overview — no page reload, instant status update.

### ✉️ AI Email Outreach
- Generates personalized cold outreach emails for each company, referencing both the product and the company's background
- One-click send via SMTP (works with Gmail, Outlook, any SMTP provider)
- Copy to clipboard option for paste-anywhere use

### 📊 Excel Export
- Export all leads for any project to a formatted `.xlsx` spreadsheet with a single click

### 🌙 Dark / Light Theme
- Full dark mode (default) and light mode toggle, persisted in `localStorage`

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.10+, Flask |
| **AI / LLM** | Groq API — Llama 3.1 8B Instant |
| **Database** | SQLite (via Python `sqlite3`) |
| **Authentication** | Flask-Login + Werkzeug (bcrypt) |
| **Company Search** | SerpAPI (Google Maps + Google Search) |
| **Web Scraping** | Requests + BeautifulSoup4 |
| **Email Sending** | Python `smtplib` + `email.mime` |
| **Excel Export** | openpyxl |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript, Jinja2 |
| **Environment** | python-dotenv |

---

## Project Structure

```
gen6/
│
├── app.py                      # Main Flask app — all routes, DB, AI helpers
├── ai_agent.py                 # AI email copywriting module (Groq)
├── cross_project_matcher.py    # AI cross-project company matching (Groq)
│
├── templates/
│   ├── base.html               # Master layout — sidebar, CSS variables, theme
│   ├── sidebar.html            # Navigation sidebar (partial)
│   ├── login.html              # Login page with CAPTCHA
│   ├── signup.html             # 3-step registration wizard
│   ├── dashboard.html          # Main lead intelligence dashboard
│   ├── chat.html               # AI Sales Advisor chat interface
│   ├── savedprojects.html      # Project listing and creation
│   ├── overview.html           # Project overview card grid
│   ├── overview_project.html   # Per-project lead qualification view
│   ├── call_for_action.html    # CTA companies + AI email modal
│   └── industry_viewed.html    # Industry portfolio analysis
│
├── static/
│   └── project_logos/          # Uploaded project logo images
│       └── default.png         # Fallback logo
│
├── leads.db                    # SQLite database (auto-created)
├── .env                        # Environment secrets (not committed)
├── requirements.txt            # Python dependencies
└── README.md
```

---

## Database Schema

The app uses a single SQLite database (`leads.db`) with 4 tables, all created automatically on first run.

### `users`
Stores registered user accounts.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment user ID |
| `username` | TEXT UNIQUE | User's email address (login identifier) |
| `password` | TEXT | bcrypt-hashed password |

### `chats` (Projects)
Each "project" is a chat row. The terms are interchangeable in the codebase.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Project ID |
| `user` | TEXT | Owner's username (email) |
| `title` | TEXT | Project/product name |
| `created_at` | TIMESTAMP | Auto-set on creation |

### `messages`
AI Sales Chat conversation history, per project.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Message ID |
| `chat_id` | INTEGER FK | → `chats.id` |
| `role` | TEXT | `user` / `assistant` / `system` |
| `content` | TEXT | HTML-formatted message content |
| `timestamp` | TIMESTAMP | Auto-set on insert |

### `products`
Stores product/project metadata and AI industry suggestions.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Product ID |
| `chat_id` | INTEGER FK | → `chats.id` |
| `product_name` | TEXT | Project name |
| `description` | TEXT | Product/service description |
| `industry_suggestions` | TEXT | JSON array of AI-suggested industries |

### `companies`
All discovered and enriched company leads, linked to a project.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Company ID |
| `name` | TEXT | Company name |
| `website` | TEXT | Company website URL |
| `phone` | TEXT | Phone number |
| `address` | TEXT | Full address string |
| `rating` | TEXT | Google Maps rating |
| `description` | TEXT | Company description |
| `email` | TEXT | Email extracted from website |
| `ceo` | TEXT | Stored as `"CEO Name\|LinkedIn URL"` |
| `company_linkedin` | TEXT | LinkedIn company page URL |
| `leadership_linkedin` | TEXT | LinkedIn individual profile URL |
| `status` | TEXT | `explore` / `cta` / `declined` |
| `chat_id` | INTEGER FK | → `chats.id` |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js (optional, not required for runtime)
- A [Groq API key](https://console.groq.com) (free tier available)
- A [SerpAPI key](https://serpapi.com) for company search
- An SMTP email account (Gmail recommended)

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/tars-technologies/gen6.git
cd gen6
```

**2. Install Python dependencies**
```bash
pip install -r requirements.txt
```

**3. Create your `.env` file**
```bash
cp .env.example .env
```
Then fill in your credentials (see [Configuration](#configuration) below).

**4. Add a default project logo**

Place a `default.png` image in `static/project_logos/`. This is used as a fallback when a project has no custom logo.

**5. Run the app**
```bash
python app.py
```

The app will be available at `http://localhost:5000`.

The SQLite database (`leads.db`) and the `static/project_logos/` folder are created automatically on first startup.

---

## Configuration

All configuration is done through a `.env` file in the project root.

```env
# ── AI (Required) ──────────────────────────────────────────────
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── Company Search (Required for lead discovery) ────────────────
# Set this inside app.py on line 34: SERP_API_KEY = "your_key_here"
# Or move it to .env and load it with os.getenv("SERP_API_KEY")

# ── Email Sending (Required for outreach) ───────────────────────
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your@email.com
SENDER_PASSWORD=your_app_password_here

# For Gmail: use an App Password (not your account password).
# Generate one at: https://myaccount.google.com/apppasswords
```

> **Note:** `SERP_API_KEY` is currently set inline in `app.py` as an empty string on line 34. Move it to `.env` and load via `os.getenv("SERP_API_KEY")` for production use.

---

## How It Works

### 1. Create a Project
Sign up or log in. Create a new project by giving it a name, a description of what you're building, and an optional logo. This creates an isolated workspace for all leads, conversations, and emails related to that product.

### 2. Chat with the AI Sales Advisor
Open the AI Chat for your project. Describe your product, your target customer, or ask for sales strategy advice. The AI advisor understands your product context and responds with specific, actionable guidance. When the AI suggests industries, they are automatically extracted and saved as your targeting preferences.

### 3. Discover Companies
Go to the Dashboard. The AI-suggested industries are pre-selected. Choose your city, add or adjust industries, and click **Find Companies**.

The targeting engine runs in 3 steps:
```
Step 1 → Search existing database for companies in that city
Step 2 → AI filters them for relevance to your product description
Step 3 → If fewer than 30 leads found, search Google Maps via SerpAPI for each industry
         └── Each result is enriched: website scraped for email, CEO LinkedIn found, company LinkedIn found
```

### 4. Qualify Leads
Go to **Overview → [Your Project]**. Every discovered company appears as a card. Click a card to see full details — address, phone, email, website, LinkedIn links, and an AI cross-project match showing which of your other projects also suit this company.

Use the action buttons to move companies through the pipeline:
- **Call For Action** — marks the company as ready for outreach
- **Decline** — removes them from active consideration (with a confirmation prompt)

Filter the view by status using the buttons at the top.

### 5. Generate & Send Emails
Go to **Call For Action**. Every company you marked as CTA appears here, grouped by project. Click **Generate Newsletter** on any company.

The AI writes a personalized cold email that:
- Opens with an observation about the company
- Introduces your product naturally
- Connects it to that company's specific situation
- Closes with a clear call-to-action

Edit the subject or body if needed, then click **Send Email** to deliver it directly — or **Copy** to use it elsewhere.

### 6. Analyze Your Pipeline
Go to **Industry Viewed** to see an AI-generated analysis of your entire sales portfolio: which companies match which of your projects, surfacing the best cross-sell opportunities.

Export any project's full lead list to Excel from the sidebar.

---

## Module Reference

### `app.py` — Main Application

**Scraping & Enrichment**

| Function | Purpose |
|---|---|
| `extract_website_data(url)` | Fetches a company website, extracts the first email found and the meta description |
| `find_ceo_with_linkedin(company_name)` | SerpAPI search for CEO name and LinkedIn profile URL |
| `find_company_and_hr_linkedin(company_name)` | SerpAPI search for company LinkedIn page and a leadership profile |
| `search_companies_maps(keyword, city)` | Main discovery function — queries Google Maps via SerpAPI and enriches each result |

**Database Helpers**

| Function | Purpose |
|---|---|
| `get_db_connection()` | Opens a SQLite connection to `leads.db` |
| `init_db()` | Creates `companies` and `users` tables, safely adds missing columns |
| `init_chat_system()` | Creates `chats`, `messages`, `products` tables |
| `save_company(c, chat_id)` | Inserts a company dict into the database |
| `get_companies(chat_id)` | Returns all companies for a project |
| `clear_companies(chat_id)` | Deletes all companies for a project (before re-search) |
| `search_existing_companies(city)` | Finds companies in the DB matching a city |
| `get_product_info(chat_id)` | Returns `(product_name, description, industry_suggestions_json)` |
| `upsert_product(...)` | Update-or-insert product metadata |

**AI Functions**

| Function | Purpose |
|---|---|
| `suggest_industries(description)` | LLM → 3-6 target industry names from a product description |
| `filter_relevant_companies(desc, companies)` | LLM → filters a company list to only relevant ones |
| `generate_sales_ai_reply(chat_id, message)` | LLM → contextual sales advisor chat reply |
| `extract_industries_from_text(text)` | Parses LLM reply for industry list items |
| `format_chat_html(text)` | Converts plaintext to safe HTML for chat storage |
| `chat_html_to_text(content)` | Converts stored chat HTML back to plaintext for LLM input |

**Chat / Project Utilities**

| Function | Purpose |
|---|---|
| `create_chat(user, title)` | Creates a new project, returns `chat_id` |
| `save_message(chat_id, role, content)` | Saves a single chat message |
| `get_user_chats()` | Returns all projects for the current user |
| `get_chat_messages(chat_id)` | Returns all messages for a project |
| `user_mentions_project(msg)` | Detects if a message describes a project being built |
| `extract_project_name(msg)` | Regex-based extraction of a project name from casual text |
| `user_requests_industry_suggestions(msg)` | Detects if the user is asking for industry recommendations |

---

### `ai_agent.py` — Email Copywriting

```python
generate_newsletter_draft(project_title, project_description, company_name, company_description)
→ { "subject": str, "body": str }
```

Uses Groq (Llama 3.1 8B, temperature 0.7) to write a personalized B2B cold outreach email under 200 words. The prompt frames the model as a B2B sales copywriter and provides both project and company context. Response is parsed as JSON with a fallback manual parser if the model wraps the output in markdown.

---

### `cross_project_matcher.py` — Cross-Project Intelligence

```python
find_matching_projects(company_name, company_description, projects)
→ ["Project A", "Project B", ...]
```

Sends all user projects plus a target company to the Groq LLM (temperature 0.3) and asks which projects best match the company. Returns a JSON array of project names. Used in the lead qualification popup to show sales reps which other products might also be relevant for a given company.

---

## API Routes

### Authentication

| Method | Route | Auth | Description |
|---|---|---|---|
| GET / POST | `/` | — | Login page |
| GET / POST | `/signup` | — | 3-step registration |
| GET | `/logout` | ✓ | Log out current user |

### Projects & Dashboard

| Method | Route | Auth | Description |
|---|---|---|---|
| GET | `/dashboard` | ✓ | Main lead dashboard |
| GET | `/savedprojects` | ✓ | View all projects |
| GET | `/open_project/<id>` | ✓ | Set active project in session |
| POST | `/new_chat` | ✓ | Create new project (with logo upload) |
| POST | `/delete_project/<id>` | ✓ | Delete project + all data |
| POST | `/run_targeting` | ✓ | Run company discovery pipeline |
| GET | `/export_excel` | ✓ | Download leads as `.xlsx` |
| GET | `/export_excel/<id>` | ✓ | Download leads for specific project |

### AI Chat

| Method | Route | Auth | Description |
|---|---|---|---|
| GET | `/chat` | ✓ | AI Chat home |
| GET | `/create_project` | ✓ | Show project creation panel |
| GET | `/chat_session/<id>` | ✓ | Open a specific chat session |
| POST | `/send_message` | — | Send chat message, get AI reply |

### Lead Qualification

| Method | Route | Auth | Description |
|---|---|---|---|
| GET | `/overview` | ✓ | Project overview grid |
| GET | `/overview_project/<id>` | ✓ | Lead qualification for one project |
| POST | `/update_status` | — | Update a company's pipeline status |
| GET | `/get_company_project_matches` | ✓ | AI cross-project match for a company |

### Outreach

| Method | Route | Auth | Description |
|---|---|---|---|
| GET | `/call_for_action` | ✓ | View CTA companies |
| POST | `/generate_newsletter` | ✓ | AI: generate cold email draft |
| POST | `/send_newsletter` | ✓ | Send email via SMTP |

### Analytics

| Method | Route | Auth | Description |
|---|---|---|---|
| GET | `/industry_viewed` | ✓ | AI industry portfolio analysis |

---

## Screenshots & Pages

| Page | Description |
|---|---|
| **Login** | Glassmorphism card with math CAPTCHA on a dark gradient |
| **Signup** | 3-step animated wizard collecting personal and company info |
| **Dashboard** | Project card grid + company leads grid + industry targeting form |
| **AI Chat** | Sidebar project list + full conversation thread per project |
| **Saved Projects** | Project cards with logo, title, description + create modal |
| **Overview** | Project grid with "Open →" buttons |
| **Lead Qualification** | Company cards with status filter buttons + detail popup modal |
| **Call For Action** | CTA companies grouped by project + AI email generation modal |
| **Industry Viewed** | AI-generated company-to-project recommendation cards |

---

## Security

- **Passwords** are hashed with `werkzeug.security.generate_password_hash` (bcrypt) — plaintext passwords are never stored
- **Authentication** is enforced on all protected routes via Flask-Login's `@login_required`
- **Data ownership** is verified by JOINing on `user = current_user.username` before returning any company or message data
- **File uploads** are validated by both MIME type and file extension — only PNG/JPEG accepted; invalid uploads trigger a rollback of the project creation
- **HTML escaping** is applied to all user-supplied text before storage via `html.escape()`
- **LLM-generated project names** are validated against the real project list before being returned to the client, preventing hallucinated data from leaking
- **SMTP email** is sent over STARTTLS (port 587) — never plaintext

> ⚠️ **For production deployments:** replace the hardcoded `app.secret_key = "tars_stable_system"` with a randomly generated secret. Use `python -c "import secrets; print(secrets.token_hex(32))"` to generate one.

---

## Known Limitations

- **SerpAPI key** is set as an empty string inline in `app.py` (line 34) — must be replaced with a real key for company discovery to work
- **SQLite** is a single-file database — not suitable for concurrent multi-user production. Migrate to PostgreSQL for production scale
- **Company enrichment is slow** — every discovered company triggers multiple SerpAPI calls for CEO and LinkedIn data. Consider batching or caching
- **Signup collects company data** (name, employees, location, etc.) but currently only `username` and `password` are stored in the database
- **`index.html`** is a legacy standalone page that is not routed in the current app — it can be safely removed
- **LLM response parsing** uses a best-effort bracket-slicing approach — occasionally a poorly formatted LLM response may result in empty results

---

## Requirements

```
flask
flask-login
werkzeug
groq
requests
beautifulsoup4
openpyxl
python-dotenv
```

Install all with:
```bash
pip install flask flask-login werkzeug groq requests beautifulsoup4 openpyxl python-dotenv
```

---

<div align="center">

**Gen6** — Built with ❤️ by TARS Technologies

*Stop searching for leads. Start closing them.*

</div>
