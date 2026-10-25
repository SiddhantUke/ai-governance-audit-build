# AI Governance Audit Platform

Upload a guideline document, extract checkable requirements from it,
audit a company's AI tool inventory against those requirements, review
low-confidence findings, and generate an audit-ready gap report with
citations.

## What it does

- **Framework library** — 19 built-in requirements from EU AI Act,
  NIST AI RMF, and ISO 42001.
- **Guideline extraction** — an LLM extracts structured requirements
  from an uploaded guideline. Every extraction must carry a verbatim
  source quote from the document, or it is rejected. This is the
  hallucination guard.
- **Deterministic rules engine** — verdicts are decided by rules, not
  by the LLM. A tool control that is present is Compliant, missing is
  a Gap, and undisclosed by the vendor is a Gap held for human review.
  Unknown is never counted as a pass.
- **Human review queue** — findings with confidence below 0.65 are
  excluded from the report until a reviewer approves or rejects them.
- **Uploaded-only audit** — an audit can run against only the
  uploaded document, with no built-in requirements mixed in.
- **Gap report** — findings with evidence needed, citations, and
  source quotes, gaps first.

## Sample inventory

The demo uses a fictional sample company with 5 AI tools across
hiring, customer support, credit decisions, marketing, and fraud
detection. The built-in audit produces 95 findings: 61 compliant,
34 gaps, 9 pending review, 86 in the report, score 70.9%.

## Tech stack

- Backend: FastAPI, SQLAlchemy (SQLite locally, Postgres-ready via
  `DATABASE_URL`)
- LLM extraction: Groq `openai/gpt-oss-120b`, temperature 0,
  reasoning effort low
- Frontend: single vanilla JavaScript page, no build step
- Auth: bcrypt password hashing, JWT, viewer / auditor / admin roles
- Tests: pytest, plus a retrieval evaluation gate

## Run locally

```bash
python -m venv .venv
# Activate the venv, then:
pip install -r requirements.txt
