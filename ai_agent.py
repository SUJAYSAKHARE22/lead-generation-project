import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found. Check your .env file.")

client = Groq(api_key=GROQ_API_KEY)


def generate_newsletter_draft(project_title, project_description,
                               company_name, company_description):

    try:
        prompt = f"""
You are a professional B2B sales copywriter specializing in technology solutions and SaaS products.

Write a personalized cold outreach email introducing our solution.

OUR SOLUTION:
Project Name: {project_title}

Project Description:
{project_description}

TARGET COMPANY:
Company Name: {company_name}

Company Details:
{company_description}

Your task:
Write a personalized cold outreach email pitching the above solution to the company.

Guidelines:
1. Open with a personalized observation about the company
2. Introduce our solution naturally
3. Explain how it solves problems relevant to the company
4. Include a clear call-to-action (demo / meeting / consultation)
5. Keep it concise and professional (under 200 words)

Return STRICT JSON ONLY:

{{
    "subject": "Email subject line",
    "body": "Full email body"
}}
"""

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are an expert B2B email copywriter."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=400
        )

        response = completion.choices[0].message.content.strip()
        print("LLM RAW RESPONSE:\n", response)

        # ===============================
        # RELIABLE PARSING (NO JSON DEPENDENCY)
        # ===============================

        cleaned = response.strip()

        # Remove markdown if present
        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()

        subject = ""
        body = ""

        try:
            data = json.loads(cleaned)
            subject = data.get("subject", "")
            body = data.get("body", "")
        except:
            # Manual extraction fallback
            if '"subject"' in cleaned and '"body"' in cleaned:
                try:
                    subject_part = cleaned.split('"subject"')[1]
                    subject = subject_part.split('"')[2]
                except:
                    subject = "Generated Outreach Email"

                body_start = cleaned.find('"body"')
                if body_start != -1:
                    body = cleaned[body_start:]
                    body = body.split(":",1)[1].strip()
                    if body.startswith('"'):
                        body = body[1:]
                    if body.endswith('"'):
                        body = body[:-1]
            else:
                subject = "Generated Outreach Email"
                body = cleaned

        return {
            "subject": subject.strip(),
            "body": body.strip()
        }

    except Exception as e:
        print("Newsletter Generation Error:", repr(e))
        return {
            "subject": "Unable to Generate Email",
            "body": "There was an issue generating the email."
        }