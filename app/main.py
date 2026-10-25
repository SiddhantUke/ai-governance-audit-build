import json
import os
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles


from app.auth import create_access_token, get_current_user, hash_password, require_role, verify_password
from app.database import SessionLocal, get_db, init_db
from app.dbmodels import AuditJob, User
from app.document import chunk_document, extract_text
from app.extraction import extract_requirements
from app.jev_judge import judge_finding
from app.report import build_report, build_report_html
from app.retrieval import RetrievalIndex
from app.rules import audit_summary, run_audit

app = FastAPI(title="AI Governance Audit Platform")
init_db()

DATA_DIR = Path(__file__).parent / "data"

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

STATE = {"findings": [], "custom_requirements": [], "custom_document": None, "custom_text": None}


def load_json(filename):
    path = DATA_DIR / filename
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def store_findings(findings):
    stored = []
    for finding in findings:
        item = finding.model_dump()
        item["id"] = f"{finding.tool_id}:{finding.requirement_id}"
        item["review_status"] = "pending" if finding.needs_review else "auto"
        item.update(judge_finding(item))
        stored.append(item)
    STATE["findings"] = stored
    return stored


def final_findings():
    return [f for f in STATE["findings"] if f["review_status"] in ("auto", "approved")]


def save_completed_job(db, owner, source, summary, stored):
    job = AuditJob(owner=owner, source=source, status="completed", summary=summary, findings=stored)
    db.add(job)
    db.commit()
    return job.id


def run_audit_job(job_id, source):
    db = SessionLocal()
    try:
        job = db.query(AuditJob).filter(AuditJob.id == job_id).first()
        if not job:
            return
        job.status = "running"
        db.commit()
        tools = load_json("inventory.json")
        if source == "uploaded_only":
            if not STATE["custom_requirements"]:
                raise ValueError("No uploaded document stored. Upload a guideline first, then run with source=uploaded_only.")
            frameworks = STATE["custom_requirements"]
        else:
            frameworks = load_json("frameworks.json") + STATE["custom_requirements"]
        findings = run_audit(frameworks, tools)
        stored = store_findings(findings)
        summary = audit_summary(findings)
        summary["total"] = len(findings)
        job.status = "completed"
        job.summary = summary
        job.findings = stored
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
    finally:
        db.commit()
        db.close()


class ExtractRequest(BaseModel):
    text: str
    source: str = "uploaded document"


class ReviewRequest(BaseModel):
    decision: str


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5


class RegisterRequest(BaseModel):
    username: str
    password: str


class PromoteRequest(BaseModel):
    username: str
    role: str


@app.get("/api/health")
def health():
    frameworks = load_json("frameworks.json")
    tools = load_json("inventory.json")
    return {
        "status": "ok",
        "step": 7,
        "frameworks": len(frameworks),
        "tools": len(tools),
    }

@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/frameworks")
def list_frameworks():
    return load_json("frameworks.json")


@app.get("/api/inventory")
def list_inventory():
    return load_json("inventory.json")


@app.post("/api/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists.")
    is_first_user = db.query(User).count() == 0
    role = "admin"
    user = User(username=req.username, hashed_password=hash_password(req.password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "role": user.role}


@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    token = create_access_token(user.username, user.role)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}


@app.post("/api/auth/promote")
def promote(req: PromoteRequest, current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    if req.role not in ("viewer", "auditor", "admin"):
        raise HTTPException(status_code=400, detail="role must be viewer, auditor, or admin.")
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.role = req.role
    db.commit()
    return {"username": user.username, "role": user.role}

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/auth/change-password")
def change_password(req: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")
    if len(req.new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="New password must be under 72 characters (bcrypt limit).")
    current_user.hashed_password = hash_password(req.new_password)
    db.commit()
    return {"username": current_user.username, "changed": True}



@app.post("/api/extract")
def extract(req: ExtractRequest, current_user: User = Depends(require_role("auditor", "admin"))):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not set. Set it in this terminal with $env:GROQ_API_KEY=... and restart the server in the same terminal.",
        )
    try:
        accepted, rejected = extract_requirements(req.text, req.source, api_key=api_key)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "source": req.source,
        "extracted": len(accepted),
        "rejected": rejected,
        "requirements": [item.model_dump() for item in accepted],
    }


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), current_user: User = Depends(require_role("auditor", "admin"))):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not set.")
    raw_bytes = await file.read()
    try:
        document_text = extract_text(file.filename, raw_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {exc}")
    if not document_text.strip():
        raise HTTPException(status_code=400, detail="Uploaded file contains no readable text.")
    chunks = chunk_document(document_text)
    try:
        accepted, rejected = extract_requirements(document_text, file.filename, api_key=api_key)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    custom = []
    for i, item in enumerate(accepted, start=1):
        data = item.model_dump()
        data["id"] = f"UP-{i:03d}"
        custom.append(data)
    STATE["custom_requirements"] = custom
    STATE["custom_document"] = file.filename
    STATE["custom_text"] = document_text
    return {
        "document": file.filename,
        "extracted": len(custom),
        "rejected": rejected,
        "chunks": len(chunks),
        "requirements": custom,
    }


@app.get("/api/custom-requirements")
def custom_requirements(current_user: User = Depends(get_current_user)):
    return {
        "document": STATE["custom_document"],
        "requirements": STATE["custom_requirements"],
    }


@app.post("/api/custom-requirements/clear")
def clear_custom(current_user: User = Depends(require_role("auditor", "admin"))):
    STATE["custom_requirements"] = []
    STATE["custom_document"] = None
    STATE["custom_text"] = None
    return {"cleared": True}


@app.post("/api/audit/run")
def audit_run(source: str = "combined", current_user: User = Depends(require_role("auditor", "admin")), db: Session = Depends(get_db)):
    if source not in ("combined", "uploaded_only"):
        raise HTTPException(status_code=400, detail="source must be 'combined' or 'uploaded_only'.")
    tools = load_json("inventory.json")
    if source == "uploaded_only":
        if not STATE["custom_requirements"]:
            raise HTTPException(status_code=400, detail="No uploaded document stored. Upload a guideline first, then run with source=uploaded_only.")
        frameworks = STATE["custom_requirements"]
    else:
        frameworks = load_json("frameworks.json") + STATE["custom_requirements"]
    findings = run_audit(frameworks, tools)
    stored = store_findings(findings)
    summary = audit_summary(findings)
    summary["total"] = len(findings)
    save_completed_job(db, current_user.username, source, summary, stored)
    return {
        **summary,
        "source": source,
        "custom_document": STATE["custom_document"],
        "findings": stored,
    }


@app.post("/api/audit/jobs")
def create_audit_job(background: BackgroundTasks, source: str = "combined", current_user: User = Depends(require_role("auditor", "admin")), db: Session = Depends(get_db)):
    if source not in ("combined", "uploaded_only"):
        raise HTTPException(status_code=400, detail="source must be 'combined' or 'uploaded_only'.")
    job = AuditJob(owner=current_user.username, source=source, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    background.add_task(run_audit_job, job.id, source)
    return {"job_id": job.id, "status": job.status, "source": source, "owner": job.owner}


@app.get("/api/audit/jobs")
def list_jobs(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(AuditJob)
    if current_user.role != "admin":
        query = query.filter(AuditJob.owner == current_user.username)
    jobs = query.order_by(AuditJob.id.desc()).all()
    return [{
        "job_id": job.id,
        "owner": job.owner,
        "source": job.source,
        "status": job.status,
        "summary": job.summary,
        "error": job.error,
    } for job in jobs]


@app.get("/api/audit/jobs/{job_id}")
def get_job(job_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(AuditJob).filter(AuditJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if current_user.role != "admin" and job.owner != current_user.username:
        raise HTTPException(status_code=403, detail="You can only view your own jobs.")
    return {
        "job_id": job.id,
        "owner": job.owner,
        "source": job.source,
        "status": job.status,
        "summary": job.summary,
        "findings": job.findings,
        "error": job.error,
    }


@app.post("/api/retrieve")
def retrieve(req: RetrieveRequest, current_user: User = Depends(get_current_user)):
    frameworks = load_json("frameworks.json")
    index = RetrievalIndex(frameworks)
    results = index.search(req.query, top_k=req.top_k)
    return {
        "query": req.query,
        "top_k": req.top_k,
        "results": results,
    }


@app.get("/api/review-queue")
def review_queue(current_user: User = Depends(require_role("auditor", "admin"))):
    return [f for f in STATE["findings"] if f["review_status"] == "pending"]


@app.post("/api/review/{finding_id}")
def review_finding(finding_id: str, req: ReviewRequest, current_user: User = Depends(require_role("auditor", "admin"))):
    if req.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'.")
    for finding in STATE["findings"]:
        if finding["id"] == finding_id:
            if finding["review_status"] != "pending":
                raise HTTPException(status_code=400, detail="This finding is not pending review.")
            finding["review_status"] = "approved" if req.decision == "approve" else "rejected"
            return finding
    raise HTTPException(status_code=404, detail="Finding not found. Run POST /api/audit/run first.")


@app.get("/api/report")
def report(current_user: User = Depends(get_current_user)):
    return build_report(final_findings())


@app.get("/api/report/html", response_class=HTMLResponse)
def report_html(current_user: User = Depends(get_current_user)):
    return build_report_html(build_report(final_findings()))
