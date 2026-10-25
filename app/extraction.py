import json
import os
import re
import time

import httpx
from pydantic import BaseModel

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """You extract checkable requirements from a guideline document.
Rules you must follow:
- Extract ONLY obligations that are actually stated in the provided document text.
- Never add requirements from your training knowledge of EU AI Act, NIST, ISO, or any other document.
- Return ONLY a JSON array, no other text, no markdown fences.
- Each item must have exactly these fields: framework, clause, obligation, risk_tier, control_type, evidence_required, source_quote.
- risk_tier must be one of: unacceptable, high, limited.
- control_type must be one of: human_oversight, logging, bias_testing, transparency, documentation, risk_assessment, incident_response, data_governance.
- source_quote must be copied WORD FOR WORD from the document text. If you cannot copy a quote word for word, do not emit that item.
- If a clause states no obligation, skip it. Do not invent one.
"""

CONTROL_WORDS = {
    "human_oversight", "logging", "bias_testing", "transparency",
    "documentation", "risk_assessment", "incident_response", "data_governance",
}


class ExtractedRequirement(BaseModel):
    framework: str
    clause: str
    obligation: str
    risk_tier: str
    control_type: str
    evidence_required: str
    source_quote: str
    confidence: float = 0.0
    needs_review: bool = False


def _normalise(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def _quote_found(quote, document_text):
    if not quote:
        return False
    return _normalise(quote) in _normalise(document_text)


def extraction_confidence(obligation, clause_text):
    score = 0.55
    lower = obligation.lower()
    if "shall" in lower or "must" in lower:
        score += 0.25
    if "evidence" in clause_text.lower():
        score += 0.10
    if any(word in lower for word in ("oversight", "logging", "bias", "transparency", "documentation", "risk", "incident", "data")):
        score += 0.08
    return round(min(score, 0.98), 4)


def _parse_json_array(content):
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("LLM did not return a JSON array")
    return data


def _call_groq(messages, api_key, use_temperature=True):
    payload = {
        "model": MODEL,
        "messages": messages,
        "reasoning_effort": "low",
        "max_completion_tokens": 2048,
    }
    if use_temperature:
        payload["temperature"] = 0
    response = httpx.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60.0,
    )
    if response.status_code == 400 and use_temperature and "temperature" in response.text.lower():
        return _call_groq(messages, api_key, use_temperature=False)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if not content or not content.strip():
        raise ValueError(
            "Groq returned empty content: gpt-oss-120b is a reasoning model, "
            "its thinking uses the same token budget as its answer. "
            "This is a hard error, never silently replaced by a template."
        )
    return content


def extract_requirements_single(document_text, source_name, api_key=None):
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError(
            "GROQ_API_KEY is not set. Set it in this terminal with "
            "$env:GROQ_API_KEY=... and restart the server in the same terminal."
        )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Source document: {source_name}\n\n{document_text}"},
    ]
    last_error = None
    for attempt in range(3):
        try:
            content = _call_groq(messages, key)
            raw_items = _parse_json_array(content)
            break
        except Exception as exc:
            last_error = exc
            status = None
            try:
                status = exc.response.status_code
            except Exception:
                status = None
            if status == 429:
                wait_seconds = 20
                try:
                    wait_seconds = int(exc.response.headers.get("retry-after", wait_seconds))
                except Exception:
                    pass
                time.sleep(wait_seconds)
                continue
            messages.append({"role": "user", "content": "Your previous output was not valid JSON. Return ONLY a JSON array, nothing else."})
    else:
        raise ValueError(f"LLM extraction failed after 3 attempts: {last_error}")

    accepted = []
    rejected = 0
    for item in raw_items:
        try:
            req = ExtractedRequirement(**item)
        except Exception:
            rejected += 1
            continue
        if not _quote_found(req.source_quote, document_text):
            rejected += 1
            continue
        req.confidence = extraction_confidence(req.obligation, document_text)
        req.needs_review = req.confidence < 0.65
        accepted.append(req)
    return accepted, rejected



def split_into_chunks(text, max_chars=4000):
    cleaned = " ".join(text.split())
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    chunks = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = (current + " " + sentence).strip() if current else sentence
        while len(current) > max_chars:
            chunks.append(current[:max_chars])
            current = current[max_chars:]
    if current:
        chunks.append(current)
    return chunks

def extract_requirements(text, document_name, api_key=None):
    if not text or not text.strip():
        return [], 0
    all_accepted = []
    total_rejected = 0
    for i, chunk in enumerate(split_into_chunks(text)):
        if i > 0:
            time.sleep(2)
        accepted, rejected = extract_requirements_single(chunk, document_name, api_key=api_key)
        total_rejected += rejected
        all_accepted.extend(accepted)
    return all_accepted, total_rejected

