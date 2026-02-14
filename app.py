import sqlite3
import requests
from flask import Flask, render_template, request, redirect, session, Response
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = "tars_stable_system"

SERP_API_KEY = "99fea23743725c92605a7f50da0558aeda96bfada39db705bbf4e1668bffd56d"  # <-- PUT YOUR REAL KEY HERE

# ===============================
# DATABASE SETUP
# ===============================

def init_db():
    conn = sqlite3.connect("leads.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        website TEXT,
        phone TEXT,
        address TEXT,
        rating TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ===============================
# GOOGLE MAPS SEARCH FUNCTION
# ===============================

def search_companies_maps(keyword, city):
    params = {
        "engine": "google_maps",
        "q": f"{keyword} company in {city}",
        "type": "search",
        "api_key": SERP_API_KEY
    }

    try:
        response = requests.get("https://serpapi.com/search", params=params)
        data = response.json()
    except:
        return []

    companies = []

    for result in data.get("local_results", []):
        name = result.get("title")
        website = result.get("website")
        phone = result.get("phone")
        address = result.get("address")
        rating = result.get("rating")

        if name and website:

            # Ensure proper URL format
            if not website.startswith("http"):
                website = "https://" + website

            companies.append({
                "name": name,
                "website": website,
                "phone": phone if phone else "",
                "address": address if address else "",
                "rating": rating if rating else ""
            })

    return companies

# ===============================
# DATABASE OPERATIONS
# ===============================

def clear_companies():
    conn = sqlite3.connect("leads.db")
    conn.execute("DELETE FROM companies")
    conn.commit()
    conn.close()

def save_company(company):
    conn = sqlite3.connect("leads.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO companies (name, website, phone, address, rating)
    VALUES (?, ?, ?, ?, ?)
    """, (
        company["name"],
        company["website"],
        company["phone"],
        company["address"],
        company["rating"]
    ))

    conn.commit()
    conn.close()

def get_companies():
    conn = sqlite3.connect("leads.db")
    cursor = conn.cursor()

    cursor.execute("SELECT name, website, phone, address, rating FROM companies")
    rows = cursor.fetchall()
    conn.close()

    companies = []
    for row in rows:
        companies.append({
            "name": row[0],
            "website": row[1],
            "phone": row[2],
            "address": row[3],
            "rating": row[4]
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
    return render_template("dashboard.html", companies=companies)

@app.route("/search", methods=["POST"])
def search():
    if "user" not in session:
        return redirect("/")

    keyword = request.form["keyword"].strip()
    city = request.form["city"].strip()

    # Clear previous results
    clear_companies()

    # Fetch new results
    companies = search_companies_maps(keyword, city)

    for company in companies:
        save_company(company)

    return redirect("/dashboard")

@app.route("/export_excel")
def export_excel():
    if "user" not in session:
        return redirect("/")

    companies = get_companies()

    if not companies:
        return redirect("/dashboard")

    wb = Workbook()
    ws = wb.active
    ws.title = "Company Leads"

    headers = ["Company Name", "Website", "Phone", "Address", "Rating"]
    ws.append(headers)

    for c in companies:
        ws.append([
            c["name"],
            c["website"],
            c["phone"],
            c["address"],
            c["rating"]
        ])

    file_path = "company_leads.xlsx"
    wb.save(file_path)

    return Response(
        open(file_path, "rb"),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment;filename=company_leads.xlsx"}
    )

@app.route("/logout")
def logout():
    session.clear()
    clear_companies()  # clear data on logout
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
