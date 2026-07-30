"""Tests for database settings, models, sessions, and migrations."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.core.config import PROJECT_ROOT, Settings, get_settings
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import (
    AgentRun,
    AgentStep,
    Analysis,
    CandidateProfile,
    Document,
    DocumentChunk,
    Job,
    User,
    UserSettings,
)
from backend.app.infrastructure.database import session as database_session
from backend.app.infrastructure.database.session import (
    DatabaseConfigurationError,
    create_session_factory,
)

TABLE_NAMES = {
    "analysis_tasks",
    "agent_runs",
    "agent_steps",
    "users",
    "candidate_profiles",
    "jobs",
    "analyses",
    "documents",
    "document_chunks",
    "user_settings",
}


def _alembic_config() -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"))


def _sqlite_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path.as_posix()}"


def test_settings_reads_database_url_from_environment(monkeypatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", database_url)

    settings = Settings(_env_file=None)

    assert settings.database_url == database_url


def test_settings_root_env_ignores_existing_llm_keys(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_PROVIDER=deepseek\nDATABASE_URL=sqlite+pysqlite:///:memory:\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(_env_file=env_file)

    assert settings.database_url == "sqlite+pysqlite:///:memory:"


def test_database_usage_without_url_raises_clear_error(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(
        database_session,
        "get_settings",
        lambda: Settings(_env_file=None),
    )

    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL is not configured"):
        database_session.create_database_engine()


def test_models_define_required_tables_and_postgresql_jsonb() -> None:
    assert set(Base.metadata.tables) == TABLE_NAMES
    assert set(User.__table__.columns.keys()) == {"id", "email", "created_at", "updated_at"}
    assert set(UserSettings.__table__.columns.keys()) == {
        "user_id",
        "display_name",
        "target_role",
        "default_analysis_options",
        "page_size",
        "show_technical_details",
        "created_at",
        "updated_at",
    }
    assert set(Document.__table__.columns.keys()) == {
        "id",
        "user_id",
        "filename",
        "file_type",
        "storage_path",
        "file_hash",
        "status",
        "created_at",
        "updated_at",
    }
    assert set(DocumentChunk.__table__.columns.keys()) == {
        "id",
        "document_id",
        "content",
        "section",
        "chunk_index",
        "embedding",
        "created_at",
    }
    assert set(Job.__table__.columns.keys()) == {
        "id",
        "user_id",
        "title",
        "company",
        "description",
        "source_url",
        "source_type",
        "job_fingerprint",
        "created_at",
        "updated_at",
    }
    assert isinstance(
        CandidateProfile.__table__.c.skills.type.dialect_impl(postgresql.dialect()),
        JSONB,
    )
    assert isinstance(
        Analysis.__table__.c.result_json.type.dialect_impl(postgresql.dialect()),
        JSONB,
    )
    assert isinstance(
        Analysis.__table__.c.evidence_json.type.dialect_impl(postgresql.dialect()),
        JSONB,
    )
    assert set(AgentRun.__table__.columns.keys()) == {
        "id", "user_id", "job_id", "status", "current_step", "result_json",
        "error_message", "created_at", "updated_at",
    }
    assert set(AgentStep.__table__.columns.keys()) == {
        "id", "run_id", "step_name", "status", "input_summary",
        "output_summary", "duration_ms", "created_at",
    }
    assert isinstance(
        AgentRun.__table__.c.result_json.type.dialect_impl(postgresql.dialect()),
        JSONB,
    )


def test_models_persist_with_sqlite_without_external_database() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        user = User(email="candidate@example.test")
        profile = CandidateProfile(
            user=user,
            name="Candidate",
            target_role="Backend Engineer",
            skills=["Python", "FastAPI"],
        )
        job = Job(
            user=user,
            title="Backend Engineer",
            company="Example",
            description="Build APIs",
            source_type="manual",
        )
        analysis = Analysis(
            user=user,
            job=job,
            candidate_profile=profile,
            status="completed",
            score=88,
            result_json={"summary": "match"},
            scoring_version="v1",
            prompt_version="v1",
            model_provider="deepseek",
            model_name="deepseek-chat",
        )
        session.add(analysis)
        session.commit()

        stored = session.scalar(select(Analysis))
        assert stored is not None
        assert stored.score == 88
        assert stored.user.email == "candidate@example.test"
        assert stored.candidate_profile.skills == ["Python", "FastAPI"]
        assert stored.created_at is not None


def test_initial_migration_upgrade_and_downgrade_on_sqlite(monkeypatch, tmp_path) -> None:
    database_url = _sqlite_url(tmp_path / "migration.db")
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _alembic_config()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert TABLE_NAMES.issubset(set(inspect(engine).get_table_names()))
    command.check(config)

    command.downgrade(config, "base")
    assert TABLE_NAMES.isdisjoint(set(inspect(engine).get_table_names()))
    engine.dispose()
    get_settings.cache_clear()


def test_analysis_task_lease_migration_round_trip(monkeypatch, tmp_path) -> None:
    database_url = _sqlite_url(tmp_path / "analysis-task-lease.db")
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _alembic_config()

    command.upgrade(config, "20260724_0009")
    engine = create_engine(database_url)
    assert "claim_token" not in {
        column["name"] for column in inspect(engine).get_columns("analysis_tasks")
    }
    engine.dispose()

    command.upgrade(config, "20260724_0010")
    engine = create_engine(database_url)
    columns = {
        column["name"] for column in inspect(engine).get_columns("analysis_tasks")
    }
    assert {"claim_token", "claimed_at", "lease_expires_at"} <= columns
    result_fk = next(
        item for item in inspect(engine).get_foreign_keys("analysis_tasks")
        if item["constrained_columns"] == ["result_id"]
    )
    assert result_fk["options"]["ondelete"] == "RESTRICT"
    engine.dispose()

    command.downgrade(config, "20260724_0009")
    engine = create_engine(database_url)
    columns = {
        column["name"] for column in inspect(engine).get_columns("analysis_tasks")
    }
    assert {"claim_token", "claimed_at", "lease_expires_at"}.isdisjoint(columns)
    result_fk = next(
        item for item in inspect(engine).get_foreign_keys("analysis_tasks")
        if item["constrained_columns"] == ["result_id"]
    )
    assert result_fk["options"]["ondelete"] == "SET NULL"
    engine.dispose()
    get_settings.cache_clear()


def test_user_settings_migration_round_trip(monkeypatch, tmp_path) -> None:
    database_url = _sqlite_url(tmp_path / "user-settings.db")
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _alembic_config()

    command.upgrade(config, "20260724_0010")
    engine = create_engine(database_url)
    assert "user_settings" not in inspect(engine).get_table_names()
    engine.dispose()

    command.upgrade(config, "20260730_0011")
    engine = create_engine(database_url)
    assert set(column["name"] for column in inspect(engine).get_columns("user_settings")) == {
        "user_id",
        "display_name",
        "target_role",
        "default_analysis_options",
        "page_size",
        "show_technical_details",
        "created_at",
        "updated_at",
    }
    engine.dispose()

    command.downgrade(config, "20260724_0010")
    engine = create_engine(database_url)
    assert "user_settings" not in inspect(engine).get_table_names()
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert "user_settings" in inspect(engine).get_table_names()
    engine.dispose()
    get_settings.cache_clear()


def test_job_fingerprint_migration_preserves_legacy_duplicates(
    monkeypatch, tmp_path
) -> None:
    database_url = _sqlite_url(tmp_path / "legacy-jobs.db")
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _alembic_config()
    command.upgrade(config, "20260720_0007")

    engine = create_engine(database_url)
    user_id = uuid.uuid4()
    first_job_id = uuid.uuid4()
    users = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("email", sa.String()),
    )
    jobs = sa.table(
        "jobs",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("title", sa.String()),
        sa.column("company", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("source_url", sa.String()),
        sa.column("source_type", sa.String()),
    )
    with engine.begin() as connection:
        connection.execute(
            users.insert().values(id=user_id, email="legacy@example.test")
        )
        connection.execute(
            jobs.insert(),
            [
                {
                    "id": first_job_id,
                    "user_id": user_id,
                    "title": "Engineer",
                    "company": "Example",
                    "description": "Build APIs",
                    "source_url": "https://example.test/jobs/1?securityId=old",
                    "source_type": "manual",
                },
                {
                    "id": uuid.uuid4(),
                    "user_id": user_id,
                    "title": "Engineer duplicate",
                    "company": "Example",
                    "description": "Changed copy",
                    "source_url": "https://example.test/jobs/1?securityId=new",
                    "source_type": "extension",
                },
            ],
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    migrated_jobs = sa.table(
        "jobs",
        sa.column("id", sa.Uuid()),
        sa.column("job_fingerprint", sa.String()),
    )
    with engine.connect() as connection:
        fingerprints = list(
            connection.scalars(select(migrated_jobs.c.job_fingerprint))
        )
    assert len(fingerprints) == 2
    assert sum(value is not None for value in fingerprints) == 1
    assert "uq_jobs_user_id_job_fingerprint" in {
        item["name"] for item in inspect(engine).get_unique_constraints("jobs")
    }
    engine.dispose()
    get_settings.cache_clear()


def test_initial_migration_renders_postgresql_jsonb_offline(monkeypatch, capsys) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@localhost:5432/ai_job_copilot",
    )
    get_settings.cache_clear()

    command.upgrade(_alembic_config(), "head", sql=True)

    migration_sql = capsys.readouterr().out
    assert "CREATE TABLE users" in migration_sql
    assert "JSONB" in migration_sql
    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration_sql
    assert "VECTOR(1024)" in migration_sql
    get_settings.cache_clear()
