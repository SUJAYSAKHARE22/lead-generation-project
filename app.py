import sqlite3
import requests
import re
import json # Added for parsing JSON from LLM
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, session, Response, jsonify
from openpyxl import Workbook
from groq import Groq # Added Groq import
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from ai_agent import generate_newsletter_draft
from cross_project_matcher import find_matching_projects

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "leads.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "project_logos")

load_dotenv(os.path.join(BASE_DIR, ".env"))  # Always load env from project folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "tars_stable_system"

SERP_API_KEY = "d35d3c85d44e533fa0e77b001b6a026d6f30ea62c6a7be49bac59d071d7637d2"


# Initialize Groq Client

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)
def get_db_connection():
    return sqlite3.connect(DB_PATH)

# ===============================
# DATABASE INIT (COMPANIES TABLE)
# ===============================
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        website TEXT,
        phone TEXT,
        address TEXT,
        rating TEXT,
        chat_id INTEGER
    )
    """)

    # Safely add new columns if not exist
    for col in [
        "description", "email", "ceo",
        "company_linkedin", "leadership_linkedin", "status"
    ]:
        try:
            cur.execute(f"ALTER TABLE companies ADD COLUMN {col} TEXT")
        except:
            pass
    # ensure chat_id exists
    try:
        cur.execute("ALTER TABLE companies ADD COLUMN chat_id INTEGER")
    except:
        pass

    # Safely add chat_id column
    try:
        cur.execute("ALTER TABLE companies ADD COLUMN chat_id INTEGER")
    except:
        pass

    conn.commit()
    conn.close()


# ===============================
# CHAT SYSTEM TABLES (NEW)
# ===============================
def init_chat_system():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        role TEXT,
        content TEXT,
        timestamp DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        product_name TEXT,
        description TEXT,
        industry TEXT,
        location TEXT,
        industry_suggestions TEXT
    )
    """)

    # add column safely if missing
    try:
        cur.execute("ALTER TABLE products ADD COLUMN industry_suggestions TEXT")
    except:
        pass

    # cleanup potential test project
    try:
        cur.execute("DELETE FROM chats WHERE title = 'Test'")
        cur.execute("DELETE FROM products WHERE chat_id NOT IN (SELECT id FROM chats)")
    except:
        pass

    conn.commit()
    conn.close()


# Run both initializations
init_db()
init_chat_system()

# ===============================
# WEBSITE SCRAPER
# ===============================
def extract_website_data(url):
    try:
        html = requests.get(url, timeout=5).text
        soup = BeautifulSoup(html, "html.parser")

        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]+", html)
        email = emails[0] if emails else ""

        desc = ""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            desc = meta.get("content", "")
        elif soup.title:
            desc = soup.title.text.strip()

        return email, desc
    except:
        return "", ""

# ===============================
# CEO LINKEDIN
# ===============================
def find_ceo_with_linkedin(company_name):
    try:
        query = f"{company_name} CEO LinkedIn"

        params = {"q": query, "engine": "google", "api_key": SERP_API_KEY}
        data = requests.get("https://serpapi.com/search", params=params).json()

        for result in data.get("organic_results", []):
            link = result.get("link", "")
            title = result.get("title", "")

            if "linkedin.com/in/" in link:
                name = title.split("-")[0].strip()
                return name, link

        return "Not Available", ""
    except:
        return "Not Available", ""

# ===============================
# COMPANY + HR LINKEDIN (NEW)
# ===============================
def find_company_and_hr_linkedin(company_name):
    try:
        query = f"{company_name} company LinkedIn"
        params = {"q": query, "engine": "google", "api_key": SERP_API_KEY}
        data = requests.get("https://serpapi.com/search", params=params).json()

        company_linkedin = ""
        leadership_linkedin = ""

        for result in data.get("organic_results", []):
            link = result.get("link", "")

            if "linkedin.com/company/" in link and not company_linkedin:
                company_linkedin = link

            if "linkedin.com/in/" in link and not leadership_linkedin:
                leadership_linkedin = link

        return company_linkedin, leadership_linkedin
    except:
        return "", ""

# ===============================
# GOOGLE MAPS SEARCH
# ===============================
def map_industry_to_search(industry):
    mapping = {
        "Industrial IoT": "automation companies",
        "Manufacturing": "manufacturing companies",
        "IT Services": "software companies",
        "Engineering Services": "engineering firms",
        "Energy": "energy companies",
        "Logistics": "logistics companies",
        "Healthcare": "hospitals",
        "Retail": "retail companies"
    }

    return mapping.get(industry, industry)

def search_companies_maps(keyword, city):
    params = {
        "engine": "google_maps",
        "q": f"{keyword} company in {city}",
        "api_key": SERP_API_KEY
    }

    data = requests.get("https://serpapi.com/search", params=params).json()
    companies = []

    for r in data.get("local_results", []):
        name = r.get("title")
        website = r.get("website")
        phone = r.get("phone", "")
        address = r.get("address", "")
        rating = r.get("rating", "")
        description = r.get("description", "")

        email = ""
        ceo = "Not Available"

        if website:
            if not website.startswith("http"):
                website = "https://" + website
            email, desc2 = extract_website_data(website)
            if not description:
                description = desc2

        # CEO enrichment
        ceo_name, ceo_link = find_ceo_with_linkedin(name)
        if ceo_link:
            ceo = f"{ceo_name}|{ceo_link}"

        # NEW LinkedIn enrichment
        company_ln, hr_ln = find_company_and_hr_linkedin(name)

        companies.append({
            "name": name,
            "website": website,
            "phone": phone,
            "address": address,
            "rating": rating,
            "description": description,
            "email": email,
            "ceo": ceo,
            "company_linkedin": company_ln,
            "leadership_linkedin": hr_ln
        })

    return companies

# ===============================
# DB OPS
# ===============================
def clear_companies(chat_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM companies WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def save_company(c, chat_id):

    conn = get_db_connection()
    conn.execute("""
INSERT INTO companies
(name, website, phone, address, rating, description,
 email, ceo, company_linkedin, leadership_linkedin, chat_id)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    c["name"],
    c["website"],
    c["phone"],
    c["address"],
    c["rating"],
    c["description"],
    c.get("email"),
    c.get("ceo"),
    c.get("company_linkedin"),
    c.get("leadership_linkedin"),
    chat_id      # ⭐ THIS IS THE IMPORTANT PART
))
    conn.commit()
    conn.close()


def get_companies(chat_id):
    conn = get_db_connection()

    rows = conn.execute("""
    SELECT name, website, phone, address, rating, description,
           email, ceo, company_linkedin, leadership_linkedin
    FROM companies
    WHERE chat_id = ?
    """, (chat_id,)).fetchall()

    conn.close()

    return [{
        "name": r[0],
        "website": r[1],
        "phone": r[2],
        "address": r[3],
        "rating": r[4],
        "description": r[5],
        "email": r[6],
        "ceo": r[7],
        "company_linkedin": r[8],
        "leadership_linkedin": r[9]
    } for r in rows]

# ===============================
# INDUSTRY SUGGESTION ENGINE
# ===============================
def suggest_industries(description):
    """
    Uses Llama 3.1 8B via Groq to dynamically detect industries 
    based on the user's product description.
    """
    try:
        # Define the available mapping keys to ensure LLM stays within bounds
        valid_industries = [
            "Industrial IoT", "Manufacturing", "IT Services", 
            "Engineering Services", "Energy", "Logistics", 
            "Healthcare", "Retail", "HR Tech", "Education", 
            "Security Solutions", "Government & Public Sector"
        ]

        prompt = f"""
        Analyze the following product/company description and identify the most relevant industries.
        Description: "{description}"

        Return ONLY a Python-style list of industries from this specific set: {valid_industries}.
        If none fit perfectly, pick the closest match or "General Business".
        Respond with ONLY the list, e.g., ["IT Services", "Manufacturing"].
        """

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that categorizes products into industries for lead generation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1, # Low temperature for consistent categorization
            max_tokens=100
        )

        # Extract content and attempt to parse the list
        response_text = completion.choices[0].message.content.strip()
        
        # Simple cleanup to handle potential LLM conversational fluff
        start_idx = response_text.find('[')
        end_idx = response_text.find(']') + 1
        if start_idx != -1 and end_idx != -1:
            industries = json.loads(response_text[start_idx:end_idx].replace("'", '"'))
            return industries
        
        return ["General Business"]
    except Exception as e:
        print(f"Groq API Error: {e}")
        return ["General Business"]


# ---------------------
# HTML formatting helper
# ---------------------

def format_chat_html(text):
    """Escape and convert simple plaintext into HTML suitable for chat bubbles.
    Preserves line breaks and converts bullets (-,*,🔹,✅) into list items with an icon.
    """
    import html
    escaped = html.escape(text)
    lines = escaped.splitlines()
    out = []
    in_ul = False
    for line in lines:
        m = re.match(r'^\s*[-*]\s+(.*)', line)
        e = re.match(r'^\s*[🔹✅•]\s*(.*)', line)
        if m or e:
            if not in_ul:
                out.append('<ul>')
                in_ul = True
            item = (m or e).group(1)
            out.append(f'<li><i class="fas fa-circle" style="font-size:0.6em;margin-right:4px;"></i>{item}</li>')
        else:
            if in_ul:
                out.append('</ul>')
                in_ul = False
            out.append(line)
    if in_ul:
        out.append('</ul>')
    return '<br>'.join(out)

# ===============================
# CHAT HELPERS (NEW)
# ===============================
def generate_sales_ai_reply(chat_id, user_message):
    try:
        previous_messages = get_chat_messages(chat_id)

# The system message defines how the assistant behaves.  It should act
        # like ChatGPT – listening to the entire conversation, sensing intent,
        # and replying as a friendly, confident human mentor rather than a
        # rigid workflow engine.
        conversation = [
            {
                "role": "system",
                "content": """
                You are an AI assistant very much like ChatGPT, taking on the role of a
                seasoned startup sales strategist chatting with a founder.

                Your responses should always consider all prior messages in the
                conversation.  Internally determine the user’s intent and craft
                full, context-aware replies that sound natural and unforced.

                Do NOT behave like a form-filling bot, and do NOT give the user
                command‑style instructions such as "say X when ready" or "type the
                word 'suggest industries'."  Speak as if you were talking to a
                friend – confident, relaxed, and adaptive to the user’s tone.

                You may gently steer the conversation when appropriate.  For
                example, once you have enough information about a project, it's
                fine to proactively offer industry suggestions or advice without
                waiting for the user to use a magic phrase.  But always stay
                conversational and avoid sounding like a checklist.

                Possible intents include greeting, casual chatter, mentioning a
                project or idea, providing a project name/description, asking for
                advice, or asking about target markets or industries.

                Your job is to:
                1. Identify the intent before replying.
                2. Respond in full sentences with a ChatGPT-like tone.
                3. Ask at most one simple, conversational follow-up question if
                   you need more details.
                4. Avoid long lists or structure unless the user specifically
                   requests it.
                5. Transition naturally from understanding the project to offering
                   suggestions or next steps when the moment feels right.
                """
            }
        ]

        for role, content, _ in previous_messages:
            conversation.append({"role": role, "content": content})

        conversation.append({"role": "user", "content": user_message})

        # allow longer replies so the assistant can craft full ChatGPT-style
        # paragraphs when appropriate
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=conversation,
            temperature=0.9,
            max_tokens=500
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        print("Sales AI Error:", e)
        return "Tell me more about what you're building."


def get_product_info(chat_id):
    """Return (product_name, description, industry_suggestions_json) for a chat if present."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT product_name, description, industry_suggestions FROM products WHERE chat_id=?",
        (chat_id,)
    ).fetchone()
    conn.close()
    if row:
        return row[0], row[1], row[2]
    return None, None, None


def upsert_product(chat_id, product_name=None, description=None, industry_suggestions=None):
    """Update the products row for chat_id if exists, otherwise insert one.
    Only non-None fields are updated.  industry_suggestions should be JSON text.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    existing = cur.execute(
        "SELECT id FROM products WHERE chat_id=?",
        (chat_id,)
    ).fetchone()

    if existing:
        updates = []
        params = []
        if product_name is not None:
            updates.append("product_name=?")
            params.append(product_name)
        if description is not None:
            updates.append("description=?")
            params.append(description)
        if industry_suggestions is not None:
            updates.append("industry_suggestions=?")
            params.append(industry_suggestions)
        if updates:
            params.append(chat_id)
            cur.execute(f"UPDATE products SET {', '.join(updates)} WHERE chat_id=?", params)
    else:
        cur.execute(
            "INSERT INTO products (chat_id, product_name, description, industry_suggestions) VALUES (?, ?, ?, ?)",
            (chat_id, product_name or "", description or "", industry_suggestions or "")
        )

    conn.commit()
    conn.close()


def user_mentions_project(msg):
    s = msg.lower()
    keywords = ["building", "build", "built", "working on", "develop", "developing", "project", "launch"]
    return any(k in s for k in keywords)


def extract_project_name(msg):
    """Try to pull a project name from an informal sentence.
    Uses simple regex heuristics; returns None if unsure.
    """
    s = msg.strip()
    # look for explicit phrases
    m = re.search(r"(?:called|named)\s+([A-Za-z0-9 _-]+)", s, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b(?:building|built|developing|working on)\s+(?:a |an |the )?([A-Za-z0-9 _-]+)", s, re.I)
    if m:
        return m.group(1).strip()
    return None


def user_requests_industry_suggestions(msg):
    s = msg.lower()
    # if the message mentions industry/market and also contains words that
    # imply a request (suggest, idea, recommend, target, where, which)
    if not ("industry" in s or "market" in s):
        return False
    keywords = ["suggest", "idea", "recommend", "target", "where", "which", "ideas"]
    return any(k in s for k in keywords)


def extract_industries_from_text(text):
    """Look for industry names in an assistant reply.

    Checks numbered or bulleted lines and also scans for known industry
    keywords. This allows us to capture the exact list the AI provided (for
    example the six-item list in the user’s attachment).
    """
    industries = []
    for line in text.splitlines():
        line = line.strip()
        # remove markdown bolding
        clean = line.replace("**", "").replace("*", "")
        # look for numbered or bulleted entries ending with a colon
        m = re.match(r'^(?:\d+\.|[-*•])\s*([^:]+):', clean)
        if m:
            industries.append(m.group(1).strip())
    # if we found nothing via bullets, fall back to capitalized phrases
    if not industries:
        caps = re.findall(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)\b", text)
        for cap in caps:
            industries.append(cap)
    # deduplicate preserving order
    seen = set()
    out = []
    for ind in industries:
        if ind not in seen:
            seen.add(ind)
            out.append(ind)
    return out

def create_chat(user, title):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO chats (user, title) VALUES (?, ?)", (user, title))
    chat_id = cur.lastrowid
    conn.commit()
    conn.close()
    return chat_id


def save_message(chat_id, role, content):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
        (chat_id, role, content)
    )
    conn.commit()
    conn.close()


def get_user_chats(user):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, title FROM chats WHERE user=? ORDER BY id DESC",
        (user,)
    ).fetchall()
    conn.close()
    return rows


def get_chat_messages(chat_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT role, content, timestamp FROM messages WHERE chat_id=? ORDER BY id ASC",
        (chat_id,)
    ).fetchall()
    conn.close()
    return rows


# ===============================
# CROSS-PROJECT INTELLIGENCE (NEW)
# ===============================

@app.route("/industry_viewed")
def industry_viewed():
    if "user" not in session:
        return redirect("/")
    
    conn = get_db_connection()
    # Fetch projects and their associated companies
    # We join chats -> products -> companies
    data = conn.execute("""
        SELECT 
            p.product_name, 
            p.description, 
            c.name, 
            c.description, 
            c.rating
        FROM products p
        JOIN chats ch ON p.chat_id = ch.id
        LEFT JOIN companies c ON ch.id = c.chat_id
        WHERE ch.user = ?
    """, (session["user"],)).fetchall()
    conn.close()

    if not data:
        return render_template("industry_viewed.html", analysis="No leads or projects found to analyze yet.")

    # Organize data for the LLM
    structured_context = {}
    for p_name, p_desc, comp_name, comp_desc, rating in data:
        if p_name not in structured_context:
            structured_context[p_name] = {"desc": p_desc, "leads": []}
        if comp_name:
            structured_context[p_name]["leads"].append(f"{comp_name} (Rating: {rating}) - {comp_desc}")

    # Build the text prompt
    context_text = "Here is the user's sales portfolio and the specific companies they have scraped:\n"
    for project, info in structured_context.items():
        context_text += f"\nPROJECT: {project}\nOFFERING: {info['desc']}\nTARGETED COMPANIES:\n"
        context_text += "\n".join(info['leads'][:10]) # Limit to top 10 leads per project for token space
        context_text += "\n"

    prompt = f"""
    Analyze the following sales projects and companies:

    {context_text}

    For each company:
    - Identify the BEST matching project(s)
    - Return ONLY valid JSON in this format:

    [
    {{
        "company": "Company Name",
        "projects": ["Project 1", "Project 2"]
    }}
    ]

    Return ONLY JSON. No explanation. No HTML.
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        response_text = completion.choices[0].message.content.strip()

        start = response_text.find("[")
        end = response_text.rfind("]") + 1

        if start != -1 and end != -1:
            json_text = response_text[start:end]
            analysis_data = json.loads(json_text)
        else:
            analysis_data = []
    except Exception as e:
        analysis_data = []
        print(f"Industry analysis error: {e}")

    return render_template("industry_viewed.html", analysis=analysis_data, active_page="industry")


# ===============================
# ROUTES (UNCHANGED)
# ===============================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "tars123":
            session["user"] = "admin"
            return redirect("/chat")
        return "Invalid Credentials"
    return render_template("login.html")
# ===============================
# CHAT ROUTES (NEW)
# ===============================

@app.route("/chat")
def chat_home():
    if "user" not in session:
        return redirect("/")

    chats = get_user_chats(session["user"])

    active_chat = session.get("active_chat")   # ✅ ADD THIS LINE

    return render_template(
        "chat.html",
        chats=chats,
        show_create=False,
        active_chat=active_chat,
        active_page="chat"
    )

@app.route("/create_project")
def create_project_page():
    if "user" not in session:
        return redirect("/")

    chats = get_user_chats(session["user"])

    return render_template(
        "chat.html",
        chats=chats,
        show_create=True
    )

@app.route("/new_chat", methods=["POST"])
def new_chat():
    if "user" not in session:
        return redirect("/")

    title = request.form.get("title", "New Project")
    description = request.form.get("description", "")

    # 1️⃣ Create chat first
    chat_id = create_chat(session["user"], title)

    # 2️⃣ Save product entry
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO products (chat_id, product_name, description) VALUES (?, ?, ?)",
        (chat_id, title, description)
    )
    conn.commit()
    conn.close()

    # 3️⃣ Save uploaded logo
    logo = request.files.get("logo")
    if logo and logo.filename != "":
        # Backend validation: allow only PNG/JPEG by MIME type and extension
        filename_raw = secure_filename(logo.filename)
        ext = filename_raw.rsplit('.', 1)[-1].lower() if '.' in filename_raw else ''
        allowed_ext = {'png', 'jpg', 'jpeg'}
        allowed_mimes = {'image/png', 'image/jpeg'}
        mime = getattr(logo, 'mimetype', '') or getattr(logo, 'content_type', '')

        if ext not in allowed_ext or mime not in allowed_mimes:
            # rollback product/chat created earlier to avoid orphan rows
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM products WHERE chat_id=?", (chat_id,))
                cur.execute("DELETE FROM chats WHERE id=?", (chat_id,))
                conn.commit()
                conn.close()
            except Exception:
                pass
            return "Invalid file type. Only PNG and JPG images are allowed.", 400

        # save file with chat_id-based filename preserving extension
        filename = secure_filename(f"{chat_id}.{ext}")
        logo_path = os.path.join(UPLOAD_FOLDER, filename)
        logo.save(logo_path)

    return redirect(f"/chat_session/{chat_id}")



@app.route("/chat_session/<int:chat_id>")
def chat_session(chat_id):
    if "user" not in session:
        return redirect("/")

    messages = get_chat_messages(chat_id)
    chats = get_user_chats(session["user"])
    session["active_chat"] = chat_id

    return render_template(
        "chat.html",
        messages=messages,
        chats=chats,
        active_chat=chat_id,
        show_create=False   # 👈 Important
    )


@app.route("/send_message", methods=["POST"])
def send_message():
    chat_id = request.form["chat_id"]
    message = request.form["message"]

    # helper for assistant replies defined here so it can access send_message scope
    def save_assistant_reply(chat_id, reply):
        save_message(chat_id, "assistant", format_chat_html(reply))
        inds = extract_industries_from_text(reply)
        if inds:
            session["suggested_industry"] = inds
            import json as _json
            upsert_product(chat_id, industry_suggestions=_json.dumps(inds))

    # persist the user's message (format for HTML)
    save_message(chat_id, "user", format_chat_html(message))

    # Conversation phase is stored per-chat in the session
    phase_key = f"phase_{chat_id}"
    phase = session.get(phase_key, "greeting")

    # Normalize incoming message
    msg_text = message.strip()

    # Phase: greeting -> detect whether user mentions a project
    if phase == "greeting":
        if user_mentions_project(msg_text):
            # try to guess a name if it's embedded in the message
            name = extract_project_name(msg_text)
            if name:
                session[f"project_name_{chat_id}"] = name
                upsert_product(chat_id, product_name=name)
                reply = f"{name} sounds interesting! Tell me more about what it does and who uses it."
            else:
                reply = "Oh nice – tell me about the project you're working on."
            session[phase_key] = "project_details"
        else:
            reply = "Hey there! I’m your sales strategist – what’s on your mind today?"

        save_assistant_reply(chat_id, reply)
        return redirect(f"/chat_session/{chat_id}")

    # Phase: expecting full project details
    if phase == "project_details":
        # if user asks about industries before giving the description, handle it
        if user_requests_industry_suggestions(msg_text):
            pname, pdesc, _ = get_product_info(chat_id)
            if not pdesc:
                reply = "I haven't got a description of the project yet – could you tell me a bit about it first?"
                save_assistant_reply(chat_id, reply)
                return redirect(f"/chat_session/{chat_id}")

            industries = suggest_industries(pdesc)
            reasons = [f"{ind}: seems relevant based on what you've shared." for ind in industries]
            reply = "Here are some industries I’d target:\n" + "\n".join(reasons)
            session["suggested_industry"] = industries
            import json as _json
            upsert_product(chat_id, industry_suggestions=_json.dumps(industries))
            save_assistant_reply(chat_id, reply)
            # remain in project_details so user can continue description if desired
            return redirect(f"/chat_session/{chat_id}")

        # otherwise treat message as project description
        project_description = msg_text
        session[f"project_description_{chat_id}"] = project_description
        upsert_product(chat_id, description=project_description)

        # Summarize understanding and also give an immediate industry hint
        pname, pdesc, _ = get_product_info(chat_id)
        industries = suggest_industries(pdesc)
        industry_msg = ""
        if industries:
            reasons = [f"{ind}: seems relevant based on the product focus." for ind in industries]
            industry_msg = "\n\nBy the way, here are a few industries that look like a good fit:\n" + "\n".join(reasons)
            # store suggestions as well
            import json as _json
            session["suggested_industry"] = industries
            upsert_product(chat_id, industry_suggestions=_json.dumps(industries))

        summary = (
            "Thanks for sharing! Here's how I understand it:\n"
            f"– Project: {pname or '(no name)'}\n"
            f"– Description: {pdesc[:800] if pdesc else '(no description)'}"
            f"{industry_msg}\n\n"
            "I've saved that for you.  If you'd like more ideas or help on next steps, just say the word – I'm here."
        )

        session[phase_key] = "idle"
        save_assistant_reply(chat_id, summary)
        return redirect(f"/chat_session/{chat_id}")

    # Phase: idle / project understood — let LLM handle general chit‑chat; only
    # intercept when the user *explicitly* wants industry ideas.
    if phase in ("idle", "project_understood"):
        if user_requests_industry_suggestions(msg_text):
            pname, pdesc, _ = get_product_info(chat_id)
            if not pdesc:
                reply = "I don't have a project description saved yet — could you tell me a bit about it first?"
                save_assistant_reply(chat_id, reply)
                return redirect(f"/chat_session/{chat_id}")

            # let the LLM craft a more descriptive reply, but always fall back
            # to a deterministic list if parsing fails
            ai_reply = generate_sales_ai_reply(chat_id, msg_text)
            inds = extract_industries_from_text(ai_reply)
            if not inds:
                inds = suggest_industries(pdesc)
            session["suggested_industry"] = inds
            import json as _json
            upsert_product(chat_id, industry_suggestions=_json.dumps(inds))
            save_assistant_reply(chat_id, ai_reply)
            return redirect(f"/chat_session/{chat_id}")

        # otherwise defer to the model for a natural conversational answer
        ai_reply = generate_sales_ai_reply(chat_id, msg_text)
        save_assistant_reply(chat_id, ai_reply)
        return redirect(f"/chat_session/{chat_id}")

    # Fallback: if phase unknown, reset to greeting and respond warmly
    session[phase_key] = "greeting"
    fallback = "Hey — tell me if you're building something, or ask me to review a project."
    save_message(chat_id, "assistant", format_chat_html(fallback))
    return redirect(f"/chat_session/{chat_id}")

@app.route("/delete_project/<int:chat_id>", methods=["POST"])
def delete_project(chat_id):
    if "user" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    # Delete related data first (to avoid orphan records)
    cur.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    cur.execute("DELETE FROM products WHERE chat_id = ?", (chat_id,))
    cur.execute("DELETE FROM companies WHERE chat_id = ?", (chat_id,))
    cur.execute("DELETE FROM chats WHERE id = ?", (chat_id,))

    conn.commit()
    conn.close()

    # Delete logo file if exists
    logo_path = os.path.join(UPLOAD_FOLDER, f"{chat_id}.png")
    if os.path.exists(logo_path):
        os.remove(logo_path)

    return "", 204

   
# ===============================
# RUN TARGETING (FROM DASHBOARD BUTTON)
# ===============================
@app.route("/run_targeting", methods=["POST"])
def run_targeting():
    if "user" not in session:
        return redirect("/")

    selected_industries = request.form.getlist("industry[]")
    city = request.form["city"]

    print("Industries received:", selected_industries)
    print("City received:", city)

    chat_id = session.get("active_chat")
    clear_companies(chat_id)

    for ind in selected_industries:
        search_keyword = map_industry_to_search(ind)
        companies = search_companies_maps(search_keyword, city)
        for c in companies:
            save_company(c, chat_id)

    session["selected_city"] = city
    session["suggested_industry"] = selected_industries

    return redirect("/dashboard")





# ===============================
# DASHBOARD PAGE
# ===============================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    chat_id = session.get("active_chat")
    companies = get_companies(chat_id)


    # try loading persisted suggestions from the product row
    suggested = []
    if chat_id:
        _, _, stored = get_product_info(chat_id)
        if stored:
            try:
                suggested = json.loads(stored)
            except:
                suggested = []
    if not suggested:
        suggested = session.get("suggested_industry", [])
    city = session.get("selected_city", "")

    print("Dashboard industries:", suggested)   # DEBUG

    return render_template(
    "dashboard.html",
    companies=companies,
    suggested_industry=suggested,
    city=city,
    active_page="dashboard"
)


@app.route("/savedprojects")
def saved_projects():
    if "user" not in session:
        return redirect("/")

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT ch.id, ch.title, p.description
        FROM chats ch
        LEFT JOIN products p ON ch.id = p.chat_id
        WHERE ch.user = ?
        ORDER BY ch.id DESC
    """, (session["user"],)).fetchall()
    conn.close()

    return render_template("savedprojects.html", chats=rows, active_page="product")

# ===============================
# OPEN SELECTED PROJECT
# ===============================
@app.route("/open_project/<int:chat_id>")
def open_project(chat_id):
    if "user" not in session:
        return redirect("/")

    # store selected project in session
    session["active_chat"] = chat_id

    return redirect("/dashboard")

@app.route("/export_excel")
def export_excel():
    if "user" not in session:
        return redirect("/")

    chat_id = session.get("active_chat")
    if not chat_id:
        return redirect("/dashboard")

    companies = get_companies(chat_id)

    conn = get_db_connection()
    row = conn.execute(
        "SELECT title FROM chats WHERE id=?",
        (chat_id,)
    ).fetchone()
    conn.close()

    if not row:
        return redirect("/dashboard")

    title = row[0]

    file_path = "company_leads.xlsx"

    if os.path.exists(file_path):
        from openpyxl import load_workbook
        wb = load_workbook(file_path)
    else:
        wb = Workbook()

    # Create new sheet with project name
    ws = wb.create_sheet(title=title[:30])  # Excel max 31 chars

    ws.append([
        "Company","Website","Phone","Address","Rating",
        "Description","Email","CEO","Company LinkedIn","Leadership LinkedIn"
    ])

    for c in companies:
        ws.append(list(c.values()))

    wb.save(file_path)

    return Response(open(file_path, "rb"),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment;filename=company_leads.xlsx"})

@app.route("/call_for_action")
def call_for_action():
    if "user" not in session:
        return redirect("/")

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT ch.id, ch.title, p.description
        FROM chats ch
        LEFT JOIN products p ON ch.id = p.chat_id
        WHERE ch.user = ?
        ORDER BY ch.id DESC
    """, (session["user"],)).fetchall()

    projects = []
    for chat_id, title, description in rows:
        company_rows = conn.execute("""
            SELECT name, description, rating, email, phone, address, website
            FROM companies
            WHERE chat_id = ? AND status = 'cta'
            ORDER BY id DESC
        """, (chat_id,)).fetchall()

        if company_rows:
            projects.append({
                "title": title,
                "description": description,
                "companies": [{
                    "name": c[0],
                    "description": c[1],
                    "rating": c[2],
                    "email": c[3],
                    "phone": c[4],
                    "address": c[5],
                    "website": c[6]
                } for c in company_rows]
            })

    conn.close()

    return render_template("call_for_action.html", projects=projects)
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/overview")
def overview():
    if "user" not in session:
        return redirect("/")

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT ch.id, ch.title, p.description
        FROM chats ch
        LEFT JOIN products p ON ch.id = p.chat_id
        WHERE ch.user = ?
        ORDER BY ch.id DESC
    """, (session["user"],)).fetchall()
    conn.close()

    return render_template("overview.html", projects=rows, active_page="overview")


@app.route("/overview_project/<int:chat_id>")
def overview_project(chat_id):
    if "user" not in session:
        return redirect("/")

    conn = get_db_connection()

    companies = conn.execute("""
        SELECT id, name, website, phone, address, rating,
               description, email, ceo,
               company_linkedin, leadership_linkedin, status
        FROM companies
        WHERE chat_id = ?
    """, (chat_id,)).fetchall()

    conn.close()

    # load product info so we can show suggested industries in the view
    pname, pdesc, stored = get_product_info(chat_id)
    suggested = []
    if stored:
        try:
            suggested = json.loads(stored)
        except:
            suggested = []

    return render_template(
        "overview_project.html",
        companies=companies,
        chat_id=chat_id,
        product_name=pname,
        product_description=pdesc,
        suggested_industry=suggested
    )

@app.route("/update_status", methods=["POST"])
def update_status():
    company_id = request.form["company_id"]
    status = request.form["status"]

    conn = get_db_connection()
    conn.execute(
        "UPDATE companies SET status=? WHERE id=?",
        (status, company_id)
    )
    conn.commit()
    conn.close()

    return "", 204

@app.route("/generate_newsletter", methods=["POST"])
def generate_newsletter():
    if "user" not in session:
        return {"error": "Unauthorized"}, 403

    project_title = request.form["project_title"]
    project_description = request.form["project_description"]
    company_name = request.form["company_name"]
    company_description = request.form.get("company_description", "")

    result = generate_newsletter_draft(
        project_title,
        project_description,
        company_name,
        company_description
    )

    return jsonify(result)

@app.route("/get_company_project_matches")
def get_company_project_matches():
    if "user" not in session:
        return {"error": "Unauthorized"}, 403

    company_id = request.args.get("company_id")

    conn = get_db_connection()

    company = conn.execute("""
        SELECT name, description
        FROM companies
        WHERE id = ?
    """, (company_id,)).fetchone()

    if not company:
        conn.close()
        return jsonify([])

    company_name, company_description = company

    # Get all projects of this user
    projects = conn.execute("""
        SELECT ch.title, p.description
        FROM chats ch
        LEFT JOIN products p ON ch.id = p.chat_id
        WHERE ch.user = ?
    """, (session["user"],)).fetchall()

    conn.close()

    matches = find_matching_projects(
        company_name,
        company_description or "",
        projects
    )

    return jsonify(matches)

if __name__ == "__main__":
    app.run(debug=True)