import sqlite3
import os
from flask import Flask, render_template, request, redirect, session, Response
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
app.secret_key = "tars_stable_system"

SERP_API_KEY = "e75cce2d188b6856848e80b7599caf9427224447b87004b883999dcde7ee96e3"

# ===============================
# DATABASE SETUP (AUTO FIX MODE)
# ===============================

def init_db():
    conn = sqlite3.connect("leads.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        url TEXT,
        location TEXT,
        score INTEGER,
        emails TEXT,
        phones TEXT
    )
    """)

    # Check if description column exists
    cursor.execute("PRAGMA table_info(companies)")
    columns = [col[1] for col in cursor.fetchall()]

    if "description" not in columns:
        cursor.execute("ALTER TABLE companies ADD COLUMN description TEXT")

    conn.commit()
    conn.close()

init_db()

# ===============================
# SIMPLE SCORING SYSTEM
# ===============================

keywords = [
    "software", "it services", "digital",
    "automation", "technology", "consulting",
    "development", "enterprise"
]

def calculate_score(text):
    score = 0
    text = text.lower()
    for word in keywords:
        if word in text:
            score += 12
    return min(score, 100)

# ===============================
# GOOGLE SEARCH
# ===============================

def search_google(query):
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERP_API_KEY
    }

    response = requests.get("https://serpapi.com/search", params=params)
    data = response.json()

    links = []
    for result in data.get("organic_results", []):
        if result.get("link"):
            links.append(result["link"])

    return links[:12]

# ===============================
# SCRAPER
# ===============================

def extract_emails(text):
    return list(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)))

def extract_phones(text):
    return list(set(re.findall(r"\+?\d[\d -]{8,}\d", text)))

def detect_city(text):
    cities = ["nagpur", "mumbai", "pune", "delhi", "bangalore", "hyderabad"]
    text = text.lower()
    for city in cities:
        if city in text:
            return city.title()
    return "Not Mentioned"

def scrape_website(url):
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text()

        return {
            "name": url.replace("https://", "").replace("http://", "").split("/")[0],
            "url": url,
            "location": detect_city(text),
            "description": text[:500].replace("\n", " "),
            "score": calculate_score(text),
            "emails": extract_emails(text),
            "phones": extract_phones(text)
        }

    except:
        return None

# ===============================
# DATABASE OPERATIONS
# ===============================

def save_company(company):
    conn = sqlite3.connect("leads.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO companies
    (name, url, location, score, emails, phones, description)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        company["name"],
        company["url"],
        company["location"],
        company["score"],
        ",".join(company["emails"]),
        ",".join(company["phones"]),
        company["description"]
    ))

    conn.commit()
    conn.close()

def get_companies():
    conn = sqlite3.connect("leads.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT name, url, location, score, emails, phones, description
    FROM companies
    ORDER BY score DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    companies = []
    for row in rows:
        companies.append({
            "name": row[0],
            "url": row[1],
            "location": row[2],
            "score": row[3],
            "emails": row[4].split(",") if row[4] else [],
            "phones": row[5].split(",") if row[5] else [],
            "description": row[6] if row[6] else ""
        })

    return companies

# ===============================
# ROUTES
# ===============================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "tars123":
            session["user"] = "admin"
            return redirect("/dashboard")
        else:
            return "Invalid Credentials"
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    companies = get_companies()

    hot = sum(1 for c in companies if c["score"] >= 60)
    warm = sum(1 for c in companies if 30 <= c["score"] < 60)
    cold = sum(1 for c in companies if c["score"] < 30)

    return render_template("dashboard.html",
                           companies=companies,
                           hot=hot,
                           warm=warm,
                           cold=cold)

@app.route("/search", methods=["POST"])
def search():
    if "user" not in session:
        return redirect("/")

    keyword = request.form["keyword"]
    city = request.form["city"]

    query = f"{keyword} company services in {city}"

    conn = sqlite3.connect("leads.db")
    conn.execute("DELETE FROM companies")
    conn.commit()
    conn.close()

    links = search_google(query)

    for link in links:
        data = scrape_website(link)
        if data:
            save_company(data)

    return redirect("/dashboard")

@app.route("/export")
def export():
    if "user" not in session:
        return redirect("/")

    companies = get_companies()

    def generate():
        yield "Company,Website,Location,Score,Emails,Phones,Description\n"
        for c in companies:
            yield f"{c['name']},{c['url']},{c['location']},{c['score']}," \
                  f"{'|'.join(c['emails'])},{'|'.join(c['phones'])}," \
                  f"\"{c['description']}\"\n"

    return Response(generate(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=tars_leads.csv"})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)