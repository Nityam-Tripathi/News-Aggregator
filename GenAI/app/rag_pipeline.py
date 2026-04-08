import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_answer(query: str, context: str):

    prompt = f"""
   You are an AI news assistant.

    Summarize the latest developments from the context.

    Instructions:
    - Cover multiple news items
    - Use bullet points if possible
    - Be clear and informative
    - Do not hallucinate

    Context:
    {context}

    Question:
    {query}
    """

    response = client.chat.completions.create(
        model = "llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return response.choices[0].message.content