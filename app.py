import sqlite3
import requests
import re
import json # Added for parsing JSON from LLM
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, session, Response
from openpyxl import Workbook
from groq import Groq # Added Groq import
import os


app = Flask(__name__)
app.secret_key = "tars_stable_system"

SERP_API_KEY = ""
GROQ_API_KEY = "" # Add your Groq API Key here
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Initialize Groq Client
client = Groq(api_key=GROQ_API_KEY)

# ===============================
# DATABASE INIT (COMPANIES TABLE)
# ===============================
def init_db():
    conn = sqlite3.connect("leads.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        website TEXT,
        phone TEXT,
        address TEXT,
        rating TEXT
    )
    """)

    # Safely add new columns if not exist
    for col in [
        "description", "email", "ceo",
        "company_linkedin", "leadership_linkedin"
    ]:
        try:
            cur.execute(f"ALTER TABLE companies ADD COLUMN {col} TEXT")
        except:
            pass

    conn.commit()
    conn.close()


# ===============================
# CHAT SYSTEM TABLES (NEW)
# ===============================
def init_chat_system():
    conn = sqlite3.connect("leads.db")
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
        location TEXT
    )
    """)

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
def clear_companies():
    conn = sqlite3.connect("leads.db")
    conn.execute("DELETE FROM companies")
    conn.commit()
    conn.close()

def save_company(c, chat_id):

    conn = sqlite3.connect("leads.db")
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
    conn = sqlite3.connect("leads.db")

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

# ===============================
# CHAT HELPERS (NEW)
# ===============================

def create_chat(user, title):
    conn = sqlite3.connect("leads.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO chats (user, title) VALUES (?, ?)", (user, title))
    chat_id = cur.lastrowid
    conn.commit()
    conn.close()
    return chat_id


def save_message(chat_id, role, content):
    conn = sqlite3.connect("leads.db")
    conn.execute(
        "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
        (chat_id, role, content)
    )
    conn.commit()
    conn.close()


def get_user_chats(user):
    conn = sqlite3.connect("leads.db")
    rows = conn.execute(
        "SELECT id, title FROM chats WHERE user=? ORDER BY id DESC",
        (user,)
    ).fetchall()
    conn.close()
    return rows


def get_chat_messages(chat_id):
    conn = sqlite3.connect("leads.db")
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE chat_id=?",
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
    
    conn = sqlite3.connect("leads.db")
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
    Analyze the following sales projects and the specific company leads found:
    {context_text}
    
    Tasks:
    1. Cross-Project Synergy: How can the 'OFFERINGS' be bundled for the 'TARGETED COMPANIES'?
    2. Lead Quality Check: Based on company descriptions, which project fits which company best?
    3. Strategic Pitch: Provide a personalized pitch for the top-rated companies mentioned.
    
    Format the response in clean HTML using <h3>, <strong>, <ul>, and <li> tags.
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        analysis_result = completion.choices[0].message.content
    except Exception as e:
        analysis_result = f"Error generating analysis: {str(e)}"

    return render_template("industry_viewed.html", analysis=analysis_result)


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
    return render_template("chat.html", chats=chats)


@app.route("/new_chat", methods=["POST"])
def new_chat():
    if "user" not in session:
        return redirect("/")

    title = request.form.get("title", "New Project")
    chat_id = create_chat(session["user"], title)

    return redirect(f"/chat_session/{chat_id}")


@app.route("/chat_session/<int:chat_id>")
def chat_session(chat_id):
    if "user" not in session:
        return redirect("/")

    messages = get_chat_messages(chat_id)
    chats = get_user_chats(session["user"])
    session["active_chat"] = chat_id
    return render_template("chat.html",
                           messages=messages,
                           chats=chats,
                           active_chat=chat_id)


@app.route("/send_message", methods=["POST"])
def send_message():
    chat_id = request.form["chat_id"]
    message = request.form["message"]

    # 1. Save what the user said
    save_message(chat_id, "user", message)

    # 2. Get the AI to suggest industries (this uses your existing function)
    industries = suggest_industries(message)
    session["suggested_industry"] = industries
    
    # 3. Create a friendly AI response for the chat UI
    industry_str = ", ".join(industries)
    ai_reply = f"I've analyzed your project. I recommend targeting: **{industry_str}**. <br><br>I've updated your Dashboard with these leads. Would you like to refine the search or view the results?"
    
    # 4. Save the AI's reply to the database so it shows up in the chat
    save_message(chat_id, "assistant", ai_reply)

    # 5. Update the product description in the DB
    conn = sqlite3.connect("leads.db")
    cur = conn.cursor()
    cur.execute("UPDATE products SET description = ? WHERE chat_id = ?", (message, chat_id))
    if cur.rowcount == 0:
        cur.execute("INSERT INTO products (chat_id, product_name, description) VALUES (?, ?, ?)", (chat_id, message, message))
    conn.commit()
    conn.close()

    # STAY in the chat so the user can see the AI's reply
    return redirect(f"/chat_session/{chat_id}")

    # Go directly to dashboard
    return redirect("/dashboard")




   
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

    clear_companies()
    chat_id = session.get("active_chat")

    for ind in selected_industries:
     search_keyword = map_industry_to_search(ind)
    companies = search_companies_maps(search_keyword, city)

    for c in companies:
        save_company(c, chat_id)   # pass chat_id here

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


    suggested = session.get("suggested_industry", [])
    city = session.get("selected_city", "")

    print("Dashboard industries:", suggested)   # DEBUG

    return render_template(
        "dashboard.html",
        companies=companies,
        suggested_industry=suggested,
        city=city
    )


@app.route("/savedprojects")
def saved_projects():
    if "user" not in session:
        return redirect("/")

    chats = get_user_chats(session["user"])   # all projects of this user

    return render_template("savedprojects.html", chats=chats)

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
    companies = get_companies()
    wb = Workbook()
    ws = wb.active

    ws.append([
        "Company","Website","Phone","Address","Rating",
        "Description","Email","CEO","Company LinkedIn","Leadership LinkedIn"
    ])

    for c in companies:
        ws.append(list(c.values()))

    path = "company_leads.xlsx"
    wb.save(path)

    return Response(open(path, "rb"),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment;filename=company_leads.xlsx"})

@app.route("/logout")
def logout():
    session.clear()
    clear_companies()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
