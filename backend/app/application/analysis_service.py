"""Job-analysis application use cases."""

import json
import os
import uuid

from sqlalchemy.orm import Session

from .crud_service import ResourceNotFoundError
from .retrieval_service import RetrievalService
from ..infrastructure.database.models import Analysis, CandidateProfile
from ..infrastructure.database.repositories import (
    AnalysisRepository,
    JobRepository,
    ProfileRepository,
    UserRepository,
)
from ..infrastructure.llm.deepseek import DeepSeekProvider
from ..infrastructure.embedding.provider import EmbeddingServiceError
from ..infrastructure.llm.parser import (
    ExtractedAnalysis,
    JobAnalysis,
    parse_analysis,
    parse_extracted_analysis,
)
from ..infrastructure.llm.provider import LLMProvider, LLMServiceError
from ..schemas.analysis import AnalysisEvidence
from ..core.security import redact_sensitive_text

SCORING_VERSION = "deterministic-v1"
PROMPT_VERSION = "retrieval-evidence-v2"
EVIDENCE_TOP_K = 2
EVIDENCE_REQUIREMENT_LIMIT = 20
EVIDENCE_MIN_SCORE = 0.35


class AnalysisService:
    """Coordinate evidence extraction and deterministic response building."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def analyze_job(
        self,
        job_title: str,
        job_description: str,
        candidate_profile: str,
    ) -> JobAnalysis:
        content = self.provider.analyze_job(job_title, job_description, candidate_profile)
        return parse_analysis(content)

    def extract_job(
        self,
        job_title: str,
        job_description: str,
        candidate_profile: str,
    ) -> ExtractedAnalysis:
        """Extract requirements and evidence statuses without calculating a score."""
        content = self.provider.analyze_job(job_title, job_description, candidate_profile)
        return parse_extracted_analysis(content)


def _profile_text(
    profile: CandidateProfile,
    evidence: list[AnalysisEvidence] | None = None,
) -> str:
    """Serialize the stored profile without inventing candidate evidence."""
    return json.dumps(
        {
            "name": profile.name,
            "target_role": profile.target_role,
            "summary": profile.summary,
            "skills": profile.skills,
            "retrieved_resume_evidence": [
                item.model_dump(mode="json") for item in evidence or []
            ],
        },
        ensure_ascii=False,
    )


class ApplicationAnalysisService:
    """Run and persist analysis for a user-owned saved job."""

    def __init__(
        self,
        session: Session,
        user_email: str,
        analyzer: AnalysisService | None = None,
        retrieval_service: RetrievalService | None = None,
    ) -> None:
        self.session = session
        self.user_email = user_email.strip().lower()
        self.analyzer = analyzer or AnalysisService(DeepSeekProvider())
        self.retrieval_service = retrieval_service
        self.users = UserRepository(session)
        self.profiles = ProfileRepository(session)
        self.jobs = JobRepository(session)
        self.analyses = AnalysisRepository(session)

    @staticmethod
    def _requirements(extracted: ExtractedAnalysis) -> list[str]:
        requirements = extracted.job_requirements
        ordered = (
            requirements.core_skills
            + requirements.preferred_skills
            + requirements.project_requirements
            + requirements.education_requirements
            + requirements.experience_requirements
        )
        unique: list[str] = []
        seen: set[str] = set()
        for requirement in ordered:
            key = " ".join(requirement.split()).casefold()
            if key and key not in seen:
                seen.add(key)
                unique.append(requirement)
        return unique[:EVIDENCE_REQUIREMENT_LIMIT]

    def _retrieve_evidence(self, extracted: ExtractedAnalysis) -> list[AnalysisEvidence]:
        if self.retrieval_service is None:
            return []
        evidence: list[AnalysisEvidence] = []
        try:
            for requirement in self._requirements(extracted):
                matches = self.retrieval_service.search(requirement, EVIDENCE_TOP_K)
                evidence.extend(
                    AnalysisEvidence(
                        chunk_id=match.chunk_id,
                        document_id=match.document_id,
                        content=redact_sensitive_text(match.content),
                        section=redact_sensitive_text(match.section),
                        requirement=redact_sensitive_text(requirement),
                    )
                    for match in matches
                    if match.score >= EVIDENCE_MIN_SCORE
                )
        except EmbeddingServiceError:
            return []
        return evidence

    def analyze_job(self, job_id: uuid.UUID) -> Analysis:
        user = self.users.get_or_create_by_email(self.user_email)
        job = self.jobs.get_for_user(job_id, user.id)
        if job is None:
            self.session.rollback()
            raise ResourceNotFoundError("job not found")

        profile = self.profiles.get_for_user(user.id)
        if profile is None:
            self.session.rollback()
            raise ResourceNotFoundError("profile not found")

        analysis = self.analyses.add(
            Analysis(
                user_id=user.id,
                job_id=job.id,
                candidate_profile_id=profile.id,
                status="pending",
                result_json={},
                evidence_json=[],
                scoring_version=SCORING_VERSION,
                prompt_version=PROMPT_VERSION,
                model_provider=os.getenv("LLM_PROVIDER", "deepseek").strip() or "deepseek",
                model_name=os.getenv("LLM_MODEL", "deepseek-chat").strip() or "deepseek-chat",
            )
        )
        self.session.commit()
        self.session.refresh(analysis)

        evidence: list[AnalysisEvidence] = []
        try:
            extracted = self.analyzer.extract_job(
                job.title,
                job.description,
                _profile_text(profile),
            )
            evidence = self._retrieve_evidence(extracted)
            result = self.analyzer.analyze_job(
                job.title,
                job.description,
                _profile_text(profile, evidence),
            )
            self.analyses.set_result(
                analysis,
                status="completed",
                score=result.score,
                result_json=result.model_dump(mode="json"),
                evidence_json=[item.model_dump(mode="json") for item in evidence],
            )
            self.session.commit()
            self.session.refresh(analysis)
            return analysis
        except Exception as exc:
            self.session.rollback()
            failure_message = (
                exc.public_message
                if isinstance(exc, LLMServiceError)
                else "analysis failed"
            )
            self.analyses.set_result(
                analysis,
                status="failed",
                score=None,
                result_json={"error": failure_message},
                evidence_json=[item.model_dump(mode="json") for item in evidence],
            )
            self.session.commit()
            raise


def analyze_job(job_title: str, job_description: str, candidate_profile: str) -> JobAnalysis:
    """Analyze a job using the configured production provider."""
    return AnalysisService(DeepSeekProvider()).analyze_job(
        job_title,
        job_description,
        candidate_profile,
    )
