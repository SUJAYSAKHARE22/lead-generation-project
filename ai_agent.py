import os
import json
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found. Check your .env file.")

client = Groq(api_key=GROQ_API_KEY)


def _normalize_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _extract_json_from_text(raw_text):
    cleaned = (raw_text or "").strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

    return None


def _first_meaningful_line(text, fallback=""):
    cleaned = _normalize_text(text)
    if not cleaned:
        return fallback

    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    for part in parts:
        candidate = part.strip()
        if len(candidate) >= 24:
            return candidate

    return cleaned[:120].rstrip(" ,.:;")


def _build_subject_fallback(company_name, project_title, project_description, company_description):
    company = _normalize_text(company_name) or "Your Team"
    project = _normalize_text(project_title) or "our solution"

    company_hint = _first_meaningful_line(company_description)
    project_hint = _first_meaningful_line(project_description, fallback="improved business outcomes")

    keyword = ""
    keyword_match = re.search(
        r"(growth|pipeline|conversion|retention|automation|efficiency|cost|revenue|acquisition)",
        f"{company_hint} {project_hint}",
        flags=re.IGNORECASE,
    )
    if keyword_match:
        keyword = keyword_match.group(1).lower()

    if keyword:
        subject = f"{company}: {project} to improve {keyword}"
    else:
        short_hint = project_hint[:45].rstrip(" ,.:;")
        subject = f"{company}: {project} for {short_hint}"

    return subject[:95].rstrip()


def _ensure_valid_subject(subject, company_name, project_title, project_description, company_description):
    candidate = _normalize_text(subject)
    invalid = {
        "",
        "subject",
        "email subject",
        "email subject line",
        "generated outreach email",
        "outreach email",
        "newsletter",
    }

    lowered = candidate.lower()
    has_min_quality = len(candidate) >= 8 and lowered not in invalid

    if not has_min_quality:
        return _build_subject_fallback(company_name, project_title, project_description, company_description)

    return candidate[:95].rstrip()


def _ensure_structured_body(body, company_name, project_title, project_description, company_description):
    if body is None:
        cleaned = ""
    elif isinstance(body, dict):
        cleaned = json.dumps(body, indent=2)
    elif isinstance(body, list):
        cleaned = "\n".join(str(item) for item in body)
    else:
        cleaned = str(body).strip()

    if cleaned and len(cleaned.split()) >= 35:
        return cleaned

    company = _normalize_text(company_name) or "your team"
    project = _normalize_text(project_title) or "our solution"
    company_context = _first_meaningful_line(company_description, fallback="your current strategic initiatives")
    project_value = _first_meaningful_line(project_description, fallback="it can reduce manual work and improve measurable outcomes")

    fallback_body = (
        f"Hi {company} Team,\n\n"
        f"I reviewed your company profile and noticed a strong alignment with {company_context}. "
        f"That is exactly why I wanted to reach out.\n\n"
        f"Our project, {project}, is designed to help teams like yours by {project_value}. "
        "It is practical to implement and focused on measurable business impact.\n\n"
        "If this sounds relevant, I can share a short tailored walkthrough with examples for your workflow. "
        "Would you be open to a 15-minute discussion next week?\n\n"
        "Best regards,"
    )

    return fallback_body


def generate_newsletter_draft(project_title, project_description,
                               company_name, company_description):
    try:
        project_title = _normalize_text(project_title)
        project_description = _normalize_text(project_description)
        company_name = _normalize_text(company_name)
        company_description = _normalize_text(company_description)

        prompt = f"""
You are a professional B2B sales copywriter specializing in technology solutions and SaaS products.
You are also an analyst who must first understand the target company deeply before writing.

Write a personalized outreach newsletter-style email introducing our solution.

OUR SOLUTION:
Project Name: {project_title}

Project Description:
{project_description}

TARGET COMPANY:
Company Name: {company_name}

Company Details:
{company_description}

Your task:
1) Analyze target company context and infer likely priorities/challenges.
2) Map our project to those priorities in a specific and realistic way.
3) Write a clean, well-structured outreach email body.
4) Generate a relevant, non-generic subject line.

Guidelines:
1. Open with a personalized observation about the company.
2. Explain the project fit in concrete business terms.
3. Keep body structure clear in 3-4 short paragraphs.
4. Include one direct CTA (demo / meeting / consultation).
5. Keep it concise and professional (120-220 words).
6. Subject must be 6-12 words, specific, and never generic.
7. Subject should mention either the company name, project focus, or business outcome.

Return STRICT JSON ONLY:
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

        parsed = _extract_json_from_text(response)
        subject = ""
        body = ""

        if isinstance(parsed, dict):
            subject = parsed.get("subject", "")
            body_raw = parsed.get("body", "")
            
            if isinstance(body_raw, dict):
                body = body_raw.get("body", "")
            elif isinstance(body_raw, list):
                body = " ".join(str(item) for item in body_raw)
            else:
                body = str(body_raw) if body_raw else ""
        else:
            # Text mode fallback when model does not return clean JSON.
            subject_match = re.search(r"subject\s*[:\-]\s*(.+)", response, re.IGNORECASE)
            if subject_match:
                subject = subject_match.group(1)
            body = response

        subject = _ensure_valid_subject(
            subject,
            company_name,
            project_title,
            project_description,
            company_description,
        )
        body = _ensure_structured_body(
            body,
            company_name,
            project_title,
            project_description,
            company_description,
        )

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