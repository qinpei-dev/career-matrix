"""Provider contract and provider-facing errors."""

from typing import Protocol


class LLMServiceError(RuntimeError):
    """An LLM failure safe to expose through the API."""

    def __init__(self, public_message: str, status_code: int = 502) -> None:
        super().__init__(public_message)
        self.public_message = public_message
        self.status_code = status_code


class LLMConfigurationError(LLMServiceError):
    """The selected LLM provider is not configured correctly."""


class LLMResponseFormatError(LLMServiceError):
    """The provider returned a response that cannot be validated."""


class LLMProvider(Protocol):
    """Contract implemented by LLM infrastructure adapters."""

    def analyze_job(
        self,
        job_title: str,
        job_description: str,
        candidate_profile: str,
    ) -> str:
        """Return the provider's raw structured-analysis content."""
        ...


class ResumeTailoringProvider(Protocol):
    """Provider contract restricted to selecting existing evidence."""

    def tailor_resume(
        self,
        job_title: str,
        job_description: str,
        resume_evidence: str,
    ) -> str:
        """Return evidence ids, ordering, and keyword classifications as JSON."""
        ...


class ProfileDraftProvider(Protocol):
    """Provider contract for extracting an unpersisted profile draft."""

    def extract_profile_draft(
        self, resume_chunks: list[dict[str, str | int]]
    ) -> str:
        """Return candidate profile fields as strict JSON."""
        ...
