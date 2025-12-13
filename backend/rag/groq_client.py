# backend/rag/groq_client.py

"""
Groq Client Wrapper
Loads API key from .env and exposes chat_with_groq() for LLM queries.
Compatible with the latest Groq Python SDK.
"""

import os
from dotenv import load_dotenv
from groq import Groq

# -------------------- Load .env --------------------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "❌ GROQ_API_KEY missing! Add it to backend/.env:\n"
        "GROQ_API_KEY=your_key_here"
    )

# -------------------- Client Init --------------------
client = Groq(api_key=GROQ_API_KEY)

# Default model (fast + stable)
DEFAULT_MODEL = "llama-3.1-8b-instant"


def chat_with_groq(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """
    Sends a prompt to Groq LLM and returns plain text response.
    Handles new SDK message format.

    Args:
        prompt: str -> User/AI combined prompt to send
        model: str  -> LLM model (default: llama-3.1-8b-instant)

    Returns:
        str: AI text response
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a smart Retail Operations AI assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        # Correct new SDK access
        return response.choices[0].message.content

    except Exception as e:
        return f"LLM error: {str(e)}"
