"""Seed idempotent local demo data without creating analyses.

Run from the repository root with::

    python -m backend.scripts.seed_demo
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.app.infrastructure.database.models import CandidateProfile, Job, User
from backend.app.infrastructure.database.session import create_database_engine

DEMO_EMAIL = "demo@example.com"
DEMO_PROFILE_NAME = "Demo Candidate"
DEMO_SKILLS = ["Python", "FastAPI", "LLM", "RAG", "Git", "Docker"]
DEMO_SUMMARY = "项目经历：AI论文格式修改Agent；CareerMatrix"


@dataclass(frozen=True)
class DemoJob:
    title: str
    description: str
    source_url: str


DEMO_JOBS = (
    DemoJob(
        title="大模型应用开发实习生",
        description="负责LLM应用开发、RAG系统构建、Python后端开发。",
        source_url="https://demo.ai-job-copilot.local/jobs/llm-application-intern",
    ),
    DemoJob(
        title="Python后端开发实习生",
        description="负责FastAPI服务开发、数据库设计、接口开发。",
        source_url="https://demo.ai-job-copilot.local/jobs/python-backend-intern",
    ),
)

LOCAL_DATABASE_HOSTS = {None, "", "localhost", "127.0.0.1", "::1", "postgres"}


def assert_development_database(database_url: str) -> None:
    """Refuse to seed a production-marked or remote database."""
    environment = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
    if environment in {"prod", "production"}:
        raise RuntimeError("Demo seed is disabled in production environments.")

    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" and url.host not in LOCAL_DATABASE_HOSTS:
        raise RuntimeError(
            f"Demo seed only supports local databases; refusing host {url.host!r}."
        )


def seed_demo(session: Session) -> tuple[User, CandidateProfile, list[Job]]:
    """Create or update the stable demo records in one transaction."""
    user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(email=DEMO_EMAIL)
        session.add(user)
        session.flush()

    profile = session.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )
    if profile is None:
        profile = CandidateProfile(user_id=user.id, name=DEMO_PROFILE_NAME, skills=[])
        session.add(profile)
    profile.name = DEMO_PROFILE_NAME
    profile.target_role = "AI应用开发工程师"
    profile.summary = DEMO_SUMMARY
    profile.skills = list(DEMO_SKILLS)

    jobs: list[Job] = []
    for demo_job in DEMO_JOBS:
        job = session.scalar(
            select(Job).where(
                Job.user_id == user.id,
                Job.source_url == demo_job.source_url,
            )
        )
        if job is None:
            job = Job(user_id=user.id, source_url=demo_job.source_url)
            session.add(job)
        job.title = demo_job.title
        job.company = "CareerMatrix"
        job.description = demo_job.description
        job.source_type = "demo"
        jobs.append(job)

    session.commit()
    return user, profile, jobs


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if database_url is None:
        from backend.app.core.config import get_settings

        database_url = get_settings().database_url

    assert_development_database(database_url)
    engine = create_database_engine(database_url)
    try:
        with Session(engine) as session:
            user, profile, jobs = seed_demo(session)
            print(f"Demo user ready: {user.email}")
            print(f"Demo profile ready: {profile.target_role}")
            print(f"Demo jobs ready: {len(jobs)}")
            print("Analyses created: 0")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
