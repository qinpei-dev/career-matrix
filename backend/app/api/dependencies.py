"""Dependencies shared by versioned API routers."""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..application.analysis_service import ApplicationAnalysisService
from ..application.analysis_service import AnalysisService
from ..application.analysis_task_service import AnalysisTaskService
from ..application.agent_service import AgentRunService
from ..application.crud_service import CrudService
from ..application.document_service import DocumentService
from ..application.profile_draft_service import ProfileDraftService
from ..application.retrieval_service import RetrievalService
from ..application.workspace_service import WorkspaceService
from ..application.tailored_resume_service import TailoredResumeService
from ..core.config import get_settings
from ..core.demo_auth import DemoAuthenticationError, authenticate_demo_token
from ..infrastructure.database.models import User
from ..infrastructure.database.repositories import UserRepository
from ..infrastructure.database.session import get_db_session
from ..infrastructure.embedding import create_embedding_provider
from ..infrastructure.embedding.provider import EmbeddingProvider
from ..infrastructure.llm.deepseek import DeepSeekProvider
from ..infrastructure.llm.provider import ResumeTailoringProvider


def get_embedding_provider() -> EmbeddingProvider:
    """Build the configured embedding adapter without making a network call."""
    return create_embedding_provider(get_settings())


def get_resume_tailoring_provider() -> ResumeTailoringProvider:
    return DeepSeekProvider()


def get_current_user(
    session: Session = Depends(get_db_session),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> User:
    """Authenticate a configured demo token and resolve its database user."""
    try:
        email = authenticate_demo_token(
            authorization,
            get_settings().demo_auth_tokens,
        )
    except DemoAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return UserRepository(session).get_or_create_by_email(email)


def get_crud_service(
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CrudService:
    """Build a request-scoped service for the authenticated demo user."""
    return CrudService(session, current_user.email)


def get_workspace_service(
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> WorkspaceService:
    """Build user-isolated dashboard, search, and settings workflows."""
    return WorkspaceService(session, current_user.email)


def get_application_analysis_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    current_user: User = Depends(get_current_user),
) -> ApplicationAnalysisService:
    """Build the saved-job analysis workflow for the authenticated demo user."""
    return ApplicationAnalysisService(
        session,
        current_user.email,
        retrieval_service=RetrievalService(
            session,
            current_user.email,
            embedding_provider,
        ),
    )


def get_document_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    current_user: User = Depends(get_current_user),
) -> DocumentService:
    """Build a request-scoped resume document workflow."""
    return DocumentService(
        session,
        current_user.email,
        get_settings().document_storage_path,
        embedding_provider,
    )


def get_profile_draft_service(
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ProfileDraftService:
    """Build the user-scoped, non-persisting profile draft workflow."""
    return ProfileDraftService(session, current_user.email, DeepSeekProvider())


def get_retrieval_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    current_user: User = Depends(get_current_user),
) -> RetrievalService:
    """Build the authenticated user's semantic retrieval workflow."""
    return RetrievalService(session, current_user.email, embedding_provider)


def get_agent_run_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    current_user: User = Depends(get_current_user),
) -> AgentRunService:
    """Build the request-scoped constrained agent workflow."""
    settings = get_settings()
    return AgentRunService(
        session,
        current_user.email,
        analyzer=AnalysisService(DeepSeekProvider()),
        retrieval_service=RetrievalService(
            session, current_user.email, embedding_provider
        ),
        timeout_seconds=settings.agent_run_timeout_seconds,
    )


def get_analysis_task_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    current_user: User = Depends(get_current_user),
) -> AnalysisTaskService:
    """Build the request-scoped persistent analysis task workflow."""
    return AnalysisTaskService(
        session,
        current_user.email,
        analyzer=AnalysisService(DeepSeekProvider()),
        retrieval_service=RetrievalService(
            session, current_user.email, embedding_provider
        ),
    )


def get_tailored_resume_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    provider: ResumeTailoringProvider = Depends(get_resume_tailoring_provider),
    current_user: User = Depends(get_current_user),
) -> TailoredResumeService:
    """Build the evidence-gated resume tailoring workflow."""
    return TailoredResumeService(
        session,
        current_user.email,
        provider=provider,
        retrieval_service=RetrievalService(
            session, current_user.email, embedding_provider
        ),
    )
