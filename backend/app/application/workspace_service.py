"""Read models and persistent preferences for the local workspace."""

from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..infrastructure.database.models import UserSettings
from ..infrastructure.database.models.analysis_task import ACTIVE_TASK_STATUSES
from ..infrastructure.database.repositories import (
    AnalysisRepository,
    AnalysisTaskRepository,
    DocumentRepository,
    JobRepository,
    UserRepository,
    UserSettingsRepository,
)
from ..schemas.workspace import (
    DashboardRead,
    DashboardStats,
    NotificationRead,
    ProviderStatus,
    ProviderStatuses,
    RecentAnalysis,
    RecentJob,
    RecentTask,
    SearchResponse,
    SearchResult,
    UserSettingsRead,
    UserSettingsUpdate,
)
from ..schemas.job import JobRead


class WorkspaceService:
    """Build user-isolated dashboard/search views and save preferences."""

    def __init__(self, session: Session, user_email: str) -> None:
        self.session = session
        self.user_email = user_email.strip().lower()
        self.users = UserRepository(session)
        self.settings = UserSettingsRepository(session)
        self.jobs = JobRepository(session)
        self.documents = DocumentRepository(session)
        self.analyses = AnalysisRepository(session)
        self.tasks = AnalysisTaskRepository(session)

    def _current_user(self):
        return self.users.get_or_create_by_email(self.user_email)

    def _settings_for_user(self, user_id) -> UserSettings:
        settings = self.settings.get_for_user(user_id)
        if settings is None:
            settings = self.settings.add(UserSettings(user_id=user_id))
        return settings

    def get_settings(self) -> UserSettingsRead:
        user = self._current_user()
        settings = self._settings_for_user(user.id)
        self.session.commit()
        self.session.refresh(settings)
        return UserSettingsRead(
            user_id=user.id,
            email=user.email,
            display_name=settings.display_name,
            target_role=settings.target_role,
            default_analysis_options=settings.default_analysis_options,
            page_size=settings.page_size,
            show_technical_details=settings.show_technical_details,
            updated_at=settings.updated_at,
        )

    def update_settings(self, payload: UserSettingsUpdate) -> UserSettingsRead:
        user = self._current_user()
        settings = self._settings_for_user(user.id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field == "default_analysis_options" and value is not None:
                value = dict(value)
            if value is not None or field == "target_role":
                setattr(settings, field, value)
        self.session.commit()
        self.session.refresh(settings)
        return self.get_settings()

    def provider_statuses(self) -> ProviderStatuses:
        runtime = get_settings()
        llm_provider = os.getenv("LLM_PROVIDER", "deepseek").strip() or "deepseek"
        llm_model = os.getenv("LLM_MODEL", "deepseek-chat").strip() or "deepseek-chat"
        llm_configured = bool(
            os.getenv("LLM_API_KEY", "").strip()
            and os.getenv("LLM_BASE_URL", "https://api.deepseek.com").strip()
        )
        embedding_configured = bool(
            runtime.embedding_api_key.strip()
            and runtime.embedding_base_url.strip()
            and runtime.embedding_model.strip()
        )
        return ProviderStatuses(
            llm=ProviderStatus(
                provider=llm_provider,
                model=llm_model,
                configured=llm_configured,
                credential="已配置（已脱敏）" if llm_configured else "未配置",
            ),
            embedding=ProviderStatus(
                provider=runtime.embedding_provider,
                model=runtime.embedding_model,
                configured=embedding_configured,
                credential="已配置（已脱敏）" if embedding_configured else "未配置",
            ),
        )

    def dashboard(self) -> DashboardRead:
        user = self._current_user()
        jobs = self.jobs.list_for_user(user.id, limit=None)
        analyses = self.analyses.list_for_user(user.id)
        documents = self.documents.list_for_user_with_chunk_count(user.id)
        tasks = self.tasks.list_for_user(user.id)
        jobs_by_id = {job.id: job for job in jobs}
        latest_by_job = {}
        for analysis in analyses:
            latest_by_job.setdefault(analysis.job_id, analysis)
        scored = [
            item.score for item in latest_by_job.values() if item.score is not None
        ]
        recent_analyses = [
            RecentAnalysis(
                id=item.id,
                job_id=item.job_id,
                job_title=jobs_by_id[item.job_id].title,
                company=jobs_by_id[item.job_id].company,
                status=item.status,
                score=item.score,
                updated_at=item.updated_at,
            )
            for item in analyses[:5]
            if item.job_id in jobs_by_id
        ]
        recent_tasks = [
            RecentTask(
                id=item.id,
                job_id=item.job_id,
                job_title=jobs_by_id[item.job_id].title,
                status=item.status,
                progress=item.progress,
                error_message=item.error_message,
                updated_at=item.updated_at,
            )
            for item in tasks[:5]
            if item.job_id in jobs_by_id
        ]
        self.session.commit()
        return DashboardRead(
            stats=DashboardStats(
                jobs=len(jobs),
                analyses=len(analyses),
                analyzed_jobs=len(latest_by_job),
                pending_jobs=len(jobs) - len(latest_by_job),
                average_score=(
                    round(sum(scored) / len(scored)) if scored else None
                ),
                high_matches=sum(score >= 80 for score in scored),
                documents=len(documents),
                ready_documents=sum(
                    document.status == "ready" for document, _ in documents
                ),
                active_tasks=sum(task.status in ACTIVE_TASK_STATUSES for task in tasks),
                failed_tasks=sum(task.status == "FAILED" for task in tasks),
            ),
            recent_jobs=[
                RecentJob(
                    **{
                        **JobRead.model_validate(job).model_dump(),
                        "analysis_status": (
                            latest_by_job[job.id].status
                            if job.id in latest_by_job
                            else None
                        ),
                        "analysis_score": (
                            latest_by_job[job.id].score
                            if job.id in latest_by_job
                            else None
                        ),
                    }
                )
                for job in jobs[:5]
            ],
            recent_analyses=recent_analyses,
            recent_tasks=recent_tasks,
        )

    @staticmethod
    def _analysis_text(result_json: dict[str, Any]) -> str:
        return json.dumps(result_json, ensure_ascii=False, default=str)

    def search(self, query: str, limit: int) -> SearchResponse:
        normalized = query.strip().casefold()
        user = self._current_user()
        jobs = self.jobs.list_for_user(user.id, limit=None)
        documents = self.documents.list_for_user_with_chunk_count(user.id)
        analyses = self.analyses.list_for_user(user.id)
        jobs_by_id = {job.id: job for job in jobs}
        results: list[SearchResult] = []
        for job in jobs:
            searchable = f"{job.title} {job.company or ''}".casefold()
            if normalized in searchable:
                results.append(SearchResult(
                    type="job", id=job.id, title=job.title,
                    subtitle=job.company or "未填写公司",
                    excerpt=job.description[:160], href=f"/jobs/{job.id}",
                    updated_at=job.updated_at,
                ))
        for document, _chunk_count in documents:
            if normalized in document.filename.casefold():
                results.append(SearchResult(
                    type="resume", id=document.id, title=document.filename,
                    subtitle=f"简历 · {document.status}",
                    excerpt="点击查看解析状态与简历分块",
                    href=f"/resumes/{document.id}", updated_at=document.updated_at,
                ))
        for analysis in analyses:
            job = jobs_by_id.get(analysis.job_id)
            result_text = self._analysis_text(analysis.result_json)
            searchable = f"{result_text} {analysis.status} {analysis.score or ''}".casefold()
            if job is not None and normalized in searchable:
                results.append(SearchResult(
                    type="analysis", id=analysis.id,
                    title=f"{job.title} · 分析结果",
                    subtitle=(
                        f"{job.company or '未填写公司'} · "
                        f"{analysis.score if analysis.score is not None else '未评分'}"
                    ),
                    excerpt=result_text[:160],
                    href=f"/jobs/{job.id}", updated_at=analysis.updated_at,
                ))
        results.sort(key=lambda item: item.updated_at, reverse=True)
        self.session.commit()
        return SearchResponse(
            query=query.strip(), total=len(results), results=results[:limit]
        )

    def notifications(self, limit: int) -> list[NotificationRead]:
        user = self._current_user()
        jobs = {
            job.id: job for job in self.jobs.list_for_user(user.id, limit=None)
        }
        tasks = self.tasks.list_for_user(user.id)
        documents = self.documents.list_for_user_with_chunk_count(user.id)
        notifications: list[NotificationRead] = []
        for task in tasks:
            job = jobs.get(task.job_id)
            if job is None or task.status not in ("COMPLETED", "FAILED"):
                continue
            failed = task.status == "FAILED"
            notifications.append(NotificationRead(
                id=f"task:{task.id}",
                level="error" if failed else "success",
                title="分析失败" if failed else "分析已完成",
                detail=task.error_message or job.title,
                href=f"/jobs/{job.id}",
                created_at=task.updated_at,
            ))
        for document, _chunk_count in documents:
            if document.status not in ("ready", "failed"):
                continue
            failed = document.status == "failed"
            notifications.append(NotificationRead(
                id=f"document:{document.id}",
                level="error" if failed else "success",
                title="简历处理失败" if failed else "简历处理完成",
                detail=document.filename,
                href=f"/resumes/{document.id}",
                created_at=document.updated_at,
            ))
        notifications.sort(key=lambda item: item.created_at, reverse=True)
        self.session.commit()
        return notifications[:limit]
