import sqlite3
import requests
import re
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, session, Response
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = "tars_stable_system"

SERP_API_KEY = "99fea23743725c92605a7f50da0558aeda96bfada39db705bbf4e1668bffd56d"

# ===============================
# DATABASE INIT (UPGRADED)
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

    # NEW columns added safely
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

init_db()

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

def save_company(c):
    conn = sqlite3.connect("leads.db")
    conn.execute("""
    INSERT INTO companies
    (name, website, phone, address, rating, description, email, ceo, company_linkedin, leadership_linkedin)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        c["name"], c["website"], c["phone"], c["address"],
        c["rating"], c["description"], c["email"], c["ceo"],
        c["company_linkedin"], c["leadership_linkedin"]
    ))
    conn.commit()
    conn.close()

def get_companies():
    conn = sqlite3.connect("leads.db")
    rows = conn.execute("""
    SELECT name, website, phone, address, rating, description, email, ceo, company_linkedin, leadership_linkedin
    FROM companies
    """).fetchall()
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
# ROUTES (UNCHANGED)
# ===============================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "tars123":
            session["user"] = "admin"
            return redirect("/dashboard")
        return "Invalid Credentials"
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html", companies=get_companies())

@app.route("/search", methods=["POST"])
def search():
    clear_companies()
    companies = search_companies_maps(
        request.form["keyword"],
        request.form["city"]
    )
    for c in companies:
        save_company(c)
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
