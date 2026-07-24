"""Dependencies shared by versioned API routers."""

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from ..application.analysis_service import ApplicationAnalysisService
from ..application.analysis_service import AnalysisService
from ..application.analysis_task_service import AnalysisTaskService
from ..application.agent_service import AgentRunService
from ..application.crud_service import DEFAULT_USER_EMAIL, CrudService
from ..application.document_service import DocumentService
from ..application.retrieval_service import RetrievalService
from ..core.config import get_settings
from ..infrastructure.database.session import get_db_session
from ..infrastructure.embedding import create_embedding_provider
from ..infrastructure.embedding.provider import EmbeddingProvider
from ..infrastructure.llm.deepseek import DeepSeekProvider


def get_embedding_provider() -> EmbeddingProvider:
    """Build the configured embedding adapter without making a network call."""
    return create_embedding_provider(get_settings())


def get_crud_service(
    session: Session = Depends(get_db_session),
    x_user_email: str = Header(
        default=DEFAULT_USER_EMAIL,
        alias="X-User-Email",
        min_length=3,
        max_length=320,
        pattern=r"^[^\s@]+@[^\s@]+$",
    ),
) -> CrudService:
    """Build a request-scoped service for the selected local user."""
    return CrudService(session, x_user_email)


def get_application_analysis_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    x_user_email: str = Header(
        default=DEFAULT_USER_EMAIL,
        alias="X-User-Email",
        min_length=3,
        max_length=320,
        pattern=r"^[^\s@]+@[^\s@]+$",
    ),
) -> ApplicationAnalysisService:
    """Build the saved-job analysis workflow for the selected local user."""
    return ApplicationAnalysisService(
        session,
        x_user_email,
        retrieval_service=RetrievalService(
            session,
            x_user_email,
            embedding_provider,
        ),
    )


def get_document_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    x_user_email: str = Header(
        default=DEFAULT_USER_EMAIL,
        alias="X-User-Email",
        min_length=3,
        max_length=320,
        pattern=r"^[^\s@]+@[^\s@]+$",
    ),
) -> DocumentService:
    """Build a request-scoped resume document workflow."""
    return DocumentService(
        session,
        x_user_email,
        get_settings().document_storage_path,
        embedding_provider,
    )


def get_retrieval_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    x_user_email: str = Header(
        default=DEFAULT_USER_EMAIL,
        alias="X-User-Email",
        min_length=3,
        max_length=320,
        pattern=r"^[^\s@]+@[^\s@]+$",
    ),
) -> RetrievalService:
    """Build the current user's semantic retrieval workflow."""
    return RetrievalService(session, x_user_email, embedding_provider)


def get_agent_run_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    x_user_email: str = Header(
        default=DEFAULT_USER_EMAIL,
        alias="X-User-Email",
        min_length=3,
        max_length=320,
        pattern=r"^[^\s@]+@[^\s@]+$",
    ),
) -> AgentRunService:
    """Build the request-scoped constrained agent workflow."""
    settings = get_settings()
    return AgentRunService(
        session,
        x_user_email,
        analyzer=AnalysisService(DeepSeekProvider()),
        retrieval_service=RetrievalService(session, x_user_email, embedding_provider),
        timeout_seconds=settings.agent_run_timeout_seconds,
    )


def get_analysis_task_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    x_user_email: str = Header(
        default=DEFAULT_USER_EMAIL,
        alias="X-User-Email",
        min_length=3,
        max_length=320,
        pattern=r"^[^\s@]+@[^\s@]+$",
    ),
) -> AnalysisTaskService:
    """Build the request-scoped persistent analysis task workflow."""
    return AnalysisTaskService(
        session,
        x_user_email,
        analyzer=AnalysisService(DeepSeekProvider()),
        retrieval_service=RetrievalService(session, x_user_email, embedding_provider),
    )
