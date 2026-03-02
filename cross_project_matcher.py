import json
from groq import Groq
import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

def find_matching_projects(company_name, company_description, projects):
    """
    projects = list of tuples [(project_name, project_description)]
    Returns list of matching project names
    """

    try:
        context = "Projects:\n"
        for p_name, p_desc in projects:
            context += f"- {p_name}: {p_desc}\n"

        prompt = f"""
        A company:

        Name: {company_name}
        Description: {company_description}

        Here are available projects:
        {context}

        Which projects best match this company?

        Return ONLY JSON in this format:
        ["Project A", "Project B"]

        If none match return [].
        """

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        text = completion.choices[0].message.content.strip()

        start = text.find("[")
        end = text.rfind("]") + 1

        if start != -1 and end != -1:
            return json.loads(text[start:end])

        return []

    except Exception as e:
        print("Cross match error:", e)
        return []