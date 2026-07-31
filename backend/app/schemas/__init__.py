"""Public API schemas."""

from .analysis import AnalysisCreate, AnalysisEvidence, AnalysisRead, JobAnalysisRead
from .analysis_task import AnalysisTaskCreate, AnalysisTaskRead, AnalysisTaskStarted
from .document import (
    DocumentChunkPublic,
    DocumentChunkRead,
    DocumentDetailRead,
    DocumentListItem,
    DocumentRead,
    DocumentUploadRead,
)
from .job import JobCreate, JobCreateResponse, JobRead
from .profile import ProfileCreate, ProfileRead, ProfileUpdate
from .retrieval import RetrievalSearchRequest, RetrievalSearchResult
from .tailored_resume import (
    TailoredItem,
    TailoredResumeCreate,
    TailoredResumeListItem,
    TailoredResumeRead,
    TailoredResumeStarted,
    TailoredResumeUpdate,
)

__all__ = [
    "AnalysisCreate",
    "AnalysisEvidence",
    "AnalysisRead",
    "AnalysisTaskCreate",
    "AnalysisTaskRead",
    "AnalysisTaskStarted",
    "DocumentChunkRead",
    "DocumentChunkPublic",
    "DocumentDetailRead",
    "DocumentListItem",
    "DocumentRead",
    "DocumentUploadRead",
    "JobAnalysisRead",
    "JobCreate",
    "JobCreateResponse",
    "JobRead",
    "ProfileCreate",
    "ProfileRead",
    "ProfileUpdate",
    "RetrievalSearchRequest",
    "RetrievalSearchResult",
    "TailoredItem",
    "TailoredResumeCreate",
    "TailoredResumeListItem",
    "TailoredResumeRead",
    "TailoredResumeStarted",
    "TailoredResumeUpdate",
]
