"""Validate LLM evidence and build the deterministic API response."""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ...services.scoring import calculate_match_score
from ...core.security import sanitize_model_payload
from .provider import LLMResponseFormatError


class JobRequirements(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    core_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    project_requirements: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    experience_requirements: list[str] = Field(default_factory=list)

    @field_validator(
        "core_skills",
        "preferred_skills",
        "project_requirements",
        "education_requirements",
        "experience_requirements",
    )
    @classmethod
    def bound_retrieval_inputs(cls, values: list[str]) -> list[str]:
        """Keep model-derived RAG queries small, factual, and finite."""
        bounded = [item.strip()[:300] for item in values[:50] if item.strip()]
        return list(dict.fromkeys(bounded))


class ExtractedAnalysis(BaseModel):
    """Structured evidence returned by the model; legacy score is ignored."""

    model_config = ConfigDict(extra="ignore", strict=True)

    job_requirements: JobRequirements = Field(default_factory=JobRequirements)
    matched_skills: list[str] = Field(default_factory=list)
    partial_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    unverified_skills: list[str] = Field(default_factory=list)
    project_evidence: list[str] = Field(default_factory=list)
    education_evidence: list[str] = Field(default_factory=list)
    experience_evidence: list[str] = Field(default_factory=list)
    project_status: Literal["direct", "related", "general", "unverified", "missing"] = "unverified"
    education_status: Literal["matched", "partial", "unverified", "missing"] = "unverified"
    experience_status: Literal["matched", "partial", "unverified", "missing"] = "unverified"
    learning_plan: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    greeting: str = "分析已完成。"
    confidence: float = Field(default=0.0, ge=0, le=1)


class ScoreDimension(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    score: int = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    applicable: bool
    reason: str = Field(min_length=1)


class ScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    core_skills: ScoreDimension
    preferred_skills: ScoreDimension
    project_experience: ScoreDimension
    education_background: ScoreDimension
    work_experience: ScoreDimension


class JobAnalysis(BaseModel):
    """Final API response after backend scoring."""

    model_config = ConfigDict(extra="forbid", strict=True)

    score: int = Field(ge=0, le=100)
    score_breakdown: ScoreBreakdown
    summary: str = Field(min_length=1)
    matched_skills: list[str]
    partial_skills: list[str]
    missing_skills: list[str]
    unverified_skills: list[str]
    project_evidence: list[str]
    education_evidence: list[str]
    experience_evidence: list[str]
    learning_plan: list[str]
    reasoning: list[str]
    greeting: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


def extract_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if not stripped:
        raise LLMResponseFormatError("模型返回格式错误")
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for index, character in enumerate(stripped):
        if character != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise LLMResponseFormatError("模型返回格式错误")


def build_final_analysis(extracted: ExtractedAnalysis) -> JobAnalysis:
    requirements = extracted.job_requirements
    calculated = calculate_match_score(
        core_skills=requirements.core_skills,
        preferred_skills=requirements.preferred_skills,
        project_requirements=requirements.project_requirements,
        education_requirements=requirements.education_requirements,
        experience_requirements=requirements.experience_requirements,
        matched_skills=extracted.matched_skills,
        partial_skills=extracted.partial_skills,
        missing_skills=extracted.missing_skills,
        unverified_skills=extracted.unverified_skills,
        project_status=extracted.project_status,
        education_status=extracted.education_status,
        experience_status=extracted.experience_status,
    )
    score = calculated["score"]
    classified = calculated["classified_skills"]
    return JobAnalysis.model_validate(
        {
            "score": score,
            "score_breakdown": calculated["score_breakdown"],
            "summary": f"按岗位明确要求和候选人证据确定性计算，综合匹配度为 {score} 分。",
            "matched_skills": classified["matched"],
            "partial_skills": classified["partial"],
            "missing_skills": classified["missing"],
            "unverified_skills": classified["unverified"],
            "project_evidence": extracted.project_evidence,
            "education_evidence": extracted.education_evidence,
            "experience_evidence": extracted.experience_evidence,
            "learning_plan": extracted.learning_plan,
            "reasoning": extracted.reasoning,
            "greeting": extracted.greeting,
            "confidence": extracted.confidence,
        }
    )


def parse_analysis(content: str) -> JobAnalysis:
    return build_final_analysis(parse_extracted_analysis(content))


def parse_extracted_analysis(content: str) -> ExtractedAnalysis:
    """Validate provider output without accepting or calculating a score."""
    try:
        return ExtractedAnalysis.model_validate(
            sanitize_model_payload(extract_json_object(content))
        )
    except (ValidationError, LLMResponseFormatError) as exc:
        raise LLMResponseFormatError("模型返回格式错误") from exc
