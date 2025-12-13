# backend/rag/ops_copilot.py

"""
Ops Copilot – Retail AI Analyst
Generates business insights + structured metadata (KPIs, tables, charts)
Works with Groq LLM and Streamlit UI
"""

from .groq_client import chat_with_groq
from ..db.db_utils import get_connection
import pandas as pd


def answer_ops_question(question: str):
    """
    Retail Ops Copilot:
    - Pulls last 14 days of sales
    - Sends question + context to Groq LLM
    - Returns:
        {
            "text": "<LLM reply>",
            "meta": {
                "kpis": {...},
                "tables": [...],
                "charts": [...]
            }
        }
    """

    # ---------------------- DB CONNECTION ----------------------
    conn = get_connection()
    if not conn:
        return {
            "text": "Database connection failed.",
            "meta": None
        }

    # ---------------------- SALES DATA (14 DAYS) ----------------------
    try:
        sales = pd.read_sql("""
            SELECT DATE(txn_timestamp) AS day, SUM(total_amount) AS sales
            FROM sales_transactions
            GROUP BY day
            ORDER BY day DESC
            LIMIT 14;
        """, conn)
    except Exception:
        sales = pd.DataFrame()

    conn.close()

    # Convert DataFrame to readable text
    sales_context = (
        sales.to_string(index=False)
        if not sales.empty
        else "No sales data available."
    )

    # ---------------------- LLM PROMPT ----------------------
    final_prompt = f"""
You are a **Senior Retail Operations Analyst**.
Your job is to analyze retail data and provide smart business insights.

Here is the last 14 days of sales:

{sales_context}

When answering the user's question, always:
- Identify trend directions (up/down/flat)
- Compare yesterday vs the previous day
- Highlight week-on-week change
- Detect anomalies (sudden drops/spikes)
- Suggest real operational causes such as:
    • stockouts
    • staffing issues
    • supply chain delays
    • pricing or promo impact
    • competitor influence
    • low footfall
- Give actionable recommendations

Now answer the question:

**{question}**
"""

    # ---------------------- CALL GROQ LLM ----------------------
    try:
        ai_text = chat_with_groq(final_prompt)
    except Exception as e:
        ai_text = f"LLM error: {e}"

    # ---------------------- BUILD META (KPIs + tables + charts) ----------------------
    meta = {}

    # KPIs (if at least 2 days of data exist)
    if not sales.empty and len(sales) >= 2:
        yesterday = sales.iloc[-1]
        prev_day = sales.iloc[-2]

        if prev_day.sales > 0:
            pct = round(((yesterday.sales - prev_day.sales) / prev_day.sales) * 100, 2)
        else:
            pct = 0

        meta["kpis"] = {
            "Yesterday Sales": f"₹{yesterday.sales:,.0f}",
            "Prev Day Sales": f"₹{prev_day.sales:,.0f}",
            "Change (%)": f"{pct}%"
        }

    # Full table
    if not sales.empty:
        meta["tables"] = [
            sales.to_dict(orient="records")
        ]

    # Sales trend chart
    if not sales.empty:
        meta["charts"] = [
            {
                "type": "line",
                "data": sales.to_dict(orient="records"),
                "x": "day",
                "y": "sales"
            }
        ]

    # ---------------------- RETURN ----------------------
    return {
        "text": ai_text,
        "meta": meta if meta else None
    }
