import sqlite3
import requests
import re
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = "tars_stable_system"

SERP_API_KEY = "7f982fb0183ac223daf3a7c19b4c6f4465db88af"

# ===============================
# DATABASE INIT
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
        rating TEXT,
        description TEXT,
        email TEXT,
        ceo TEXT,
        company_linkedin TEXT,
        leadership_linkedin TEXT
    )
    """)

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
        url = "https://google.serper.dev/search"

        payload = {
            "q": f"{company_name} CEO site:linkedin.com/in",
            "gl": "in",
            "hl": "en"
        }

        headers = {
            "X-API-KEY": SERP_API_KEY,
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        for result in data.get("organic", []):
            link = result.get("link", "")
            title = result.get("title", "")

            if "linkedin.com/in/" in link:
                name = title.split("-")[0].strip()
                return name, link

        return "Not Available", ""

    except:
        return "Not Available", ""


# ===============================
# COMPANY LINKEDIN
# ===============================
def find_company_and_hr_linkedin(company_name):
    try:
        url = "https://google.serper.dev/search"

        payload = {
            "q": f"{company_name} site:linkedin.com/company",
            "gl": "in",
            "hl": "en"
        }

        headers = {
            "X-API-KEY": SERP_API_KEY,
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        for result in data.get("organic", []):
            link = result.get("link", "")

            if "linkedin.com/company/" in link:
                return link, ""

        return "", ""

    except:
        return "", ""


# ===============================
# PRODUCT KEYWORD EXTRACTION
# ===============================
def extract_product_keywords(user_message):
    text = user_message.lower()
    important_words = [
        "healthcare", "hospital", "erp",
        "automation", "document", "saas",
        "software", "enterprise"
    ]

    return [word for word in important_words if word in text]

# ===============================
# COMPANY SCORING
# ===============================
def calculate_fit_score(product_keywords, company):
    score = 0
    reasons = []

    company_text = (company["description"] or "").lower()

    for keyword in product_keywords:
        if keyword in company_text:
            score += 2
            reasons.append(f"Matches '{keyword}' domain")

    if "healthcare" in company_text:
        score += 2
        reasons.append("Works in healthcare domain")

    if "erp" in company_text:
        score += 2
        reasons.append("Provides ERP solutions")

    if "automation" in company_text:
        score += 2
        reasons.append("Provides automation services")

    return score, reasons

# ===============================
# ROUTES
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
    return render_template("dashboard.html")

# ===============================
# CHATBOT ROUTE
# ===============================
@app.route("/chat", methods=["POST"])
def chat():

    if "user" not in session:
        return jsonify({"response": "Please login first."})

    data = request.get_json()
    user_message = data.get("message")

    # Detect city
    city_match = re.search(r"in ([A-Za-z ]+)", user_message)
    city = city_match.group(1) if city_match else "India"

    product_keywords = extract_product_keywords(user_message)

    search_queries = [
        "IT company",
        "software company",
        "healthcare software company",
        "ERP company",
        "hospital management software company"
    ]

    all_companies = []

    # SEARCH
    for query in search_queries:

     url = "https://google.serper.dev/maps"

    payload = {
        "q": f"{query} in {city}",
        "gl": "in",
        "hl": "en"
    }

    headers = {
        "X-API-KEY": SERP_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()

    results = data.get("places", [])

    for r in results:

        name = r.get("title")
        website = r.get("website")
        phone = r.get("phoneNumber", "")
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

        # LinkedIn enrichment
        company_ln, hr_ln = find_company_and_hr_linkedin(name)

        all_companies.append({
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


    # Remove duplicates
    unique_companies = {c["name"]: c for c in all_companies}.values()

    if not unique_companies:
        return jsonify({"response": "❌ No companies found. Check API key or city."})

    # SCORE
    scored = []
    for company in unique_companies:
        score, reasons = calculate_fit_score(product_keywords, company)
        scored.append((score, reasons, company))

    scored.sort(reverse=True, key=lambda x: x[0])

    # RESPONSE
    response = "<b>🎯 Best Companies To Pitch (Ranked)</b><br><br>"

    for score, reasons, c in scored[:5]:

        ceo_name = c["ceo"].split("|")[0] if "|" in c["ceo"] else c["ceo"]
        ceo_link = c["ceo"].split("|")[1] if "|" in c["ceo"] else ""

        reason_text = "<br>".join([f"✔ {r}" for r in reasons]) if reasons else "General IT company"

        response += f"""
        <b>{c['name']}</b><br>
        ⭐ Fit Score: {score}<br>
        Why Suitable:<br>
        {reason_text}<br><br>
        📍 {c['address']}<br>
        🌐 <a href="{c['website']}" target="_blank">Website</a><br>
        👤 CEO: {ceo_name}<br>
        🔗 CEO LinkedIn: <a href="{ceo_link}" target="_blank">{ceo_link}</a><br>
        🏢 Company LinkedIn: <a href="{c['company_linkedin']}" target="_blank">{c['company_linkedin']}</a><br>
        📧 Email: {c['email']}<br>
        ⭐ Google Rating: {c['rating']}<br>
        <hr>
        """

    return jsonify({"response": response})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
