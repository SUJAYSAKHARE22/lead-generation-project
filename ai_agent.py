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
You are a professional B2B sales copywriter specializing in CRM and lead generation solutions.

Write a personalized cold outreach email to pitch our AI-powered CRM and lead generation platform.

OUR SOLUTION:
LeadPilotGen6 - An intelligent CRM and lead generation platform that helps businesses:
- Automatically discover and qualify potential clients
- Manage customer relationships efficiently
- Automate outreach and follow-ups
- Track sales pipeline and conversions
- Generate AI-powered insights

PITCH CONTEXT:
We noticed {company_name} could benefit from our solution based on their industry and business model.

TARGET COMPANY:
{company_name}
{company_description}

Write a compelling email that:
1. Opens with a personalized observation about their company
2. Introduces our CRM/lead generation platform and its key benefits
3. Explains specifically how it can solve their business challenges
4. Includes a clear call-to-action (schedule a demo, free trial, or consultation)
5. Keeps it concise and professional (under 200 words)

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