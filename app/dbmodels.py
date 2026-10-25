from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, JSON, String
from app.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="viewer")
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditJob(Base):
    __tablename__ = "audit_jobs"
    id = Column(Integer, primary_key=True, index=True)
    owner = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    summary = Column(JSON, nullable=True)
    findings = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
