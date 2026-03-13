import os
import json
import math
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
def format_timestamp(seconds: float) -> str:
    seconds = int(round(float(seconds)))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
def summarize_annotations(items):
    context = "\n".join(
        f"[{float(i['timestamp']):.3f}] {i['content']}"
        for i in items
    )

    prompt = f"""
        You are a precise summarization assistant.

        You are given an ordered list of timestamped video annotations in the format:
        [TIMESTAMP_IN_SECONDS] content

        Your task is to generate a structured summary.

        Return ONLY valid JSON (no markdown, no explanations, no extra text) with the following structure:

        {{
        "tldr": "2–3 lines, clear and informative, maximum 250 words total",
        "highlights": [
            {{
            "title": "6–10 word headline",
            "timestamp": number (must match an existing timestamp from the input),
            "short": "1 sentence explanation (10–30 words)"
            }}
        ],
        "keywords": ["up to 5 concise keywords or short phrases"]
        }}

        Rules:
        - The TLDR must be at least 2 lines and at most 4 lines.
        - The TLDR must not exceed 250 words.
        - Focus on key decisions, numbers, actions, or important insights.
        - Do NOT invent information not present in the annotations.
        - For highlights, choose the most significant moments.
        - The timestamp field must exactly match one of the input timestamps.
        - Maximum 3 highlights.
        - Keep wording clear, factual, and concise.

        Annotations:
        {context}
    """

    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
        temperature=0.2,
    )

    text = response.output_text

    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except:
        return {"tldr": "", "highlights": [], "keywords": []}

def postprocess_highlights_time(summary: dict) -> dict:
    highlights = summary.get("highlights", [])
    if not isinstance(highlights, list):
        return summary

    for h in highlights:
        ts = h.get("timestamp", None)
        if ts is None:
            continue
        try:
            h["timestamp_display"] = format_timestamp(ts)
        except Exception:
            pass
    return summary

if __name__ == "__main__":
    sample = [
        {"timestamp": 12.3, "content": "We expect Q3 revenue to grow 12% year-on-year."},
        {"timestamp": 20.0, "content": "Hiring freeze for next quarter to manage costs."},
        {"timestamp": 22.0, "content": "Prioritize project X over Y; pause non-critical work."},
        {"timestamp": 105.4, "content": "Customer feedback: strong interest in a mobile widget."},
        {"timestamp": 210.0, "content": "Goal: reduce time-to-market by 20%."},
    ]

    out = summarize_annotations(sample)
    out = postprocess_highlights_time(out)
    print(json.dumps(out, indent=2))

