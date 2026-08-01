"""Generate an unpersisted candidate profile draft from owned resume chunks."""

from __future__ import annotations

import json
import re
import unicodedata
import uuid

from collections.abc import Iterable

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..core.security import (
    contains_untrusted_command,
    redact_sensitive_text,
    sanitize_model_text,
)
from ..infrastructure.database.models import DocumentChunk
from ..infrastructure.database.repositories import DocumentRepository, UserRepository
from ..infrastructure.llm.provider import (
    LLMResponseFormatError,
    ProfileDraftProvider,
)
from ..schemas.profile import (
    ProfileDraftEvidence,
    ProfileDraftName,
    ProfileDraftRead,
    ProfileDraftSkill,
    ProfileDraftSummary,
    ProfileDraftTargetRole,
)
from .crud_service import ResourceConflictError, ResourceNotFoundError

MAX_PROFILE_DRAFT_INPUT_CHARS = 50_000


class ProfileDraftExtractionError(RuntimeError):
    """The selected document cannot provide usable profile draft input."""


class ProfileDraftEvidenceError(ProfileDraftExtractionError):
    """Model evidence does not belong to the selected document or match its text."""


NEGATED_SKILL_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"没有.{0,24}",
        r"未使用.{0,24}",
        r"不了解.{0,24}",
        r"不熟悉.{0,24}",
        r"暂无.{0,12}经验",
        r"未接触.{0,24}",
        r"不具备.{0,24}",
        r"不会.{0,24}",
        r"从未(?:使用|接触|学习).{0,24}",
        r"经验\s*[:：]\s*(?:无|没有|零|0)",
        r"\bno\s+(?:experience|knowledge|familiarity)\s+(?:with|in)\b",
        r"\bno\b.{0,24}\b(?:experience|knowledge|familiarity)\b",
        r"\bnot\s+(?:used|familiar with|experienced with)\b",
        r"\b(?:never\s+used|without|lack(?:s|ing)?)\b.{0,24}",
    )
)

PROFILE_INSTRUCTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bsystem\s*:",
        r"\bassistant\s*:",
        r"请.{0,12}(?:输出|加入|添加|列出).{0,20}技能",
        r"(?:输出|加入|添加|列为).{0,20}(?:技能|skill)",
        r"(?:include|add|return|output|list).{0,24}(?:as\s+)?(?:a\s+)?skill",
        r"\b(?:must|should)\s+(?:appear|be\s+included|be\s+listed|be\s+returned)\b",
        r"\b(?:treat|rewrite|present|describe|portray|claim)\b.{0,40}"
        r"\b(?:as|profile|candidate|skill|capability)\b",
        r"(?:将|把).{0,30}(?:写成|视为|描述为|作为|列入|加入)",
        r"(?:资料|档案|简介|结果).{0,20}(?:必须|应当|需要).{0,20}(?:包含|显示|写入)",
    )
)

NAME_EVIDENCE_SECTIONS = frozenset({"general", "contact", "个人信息", "基本信息"})
TARGET_ROLE_EVIDENCE_SECTIONS = frozenset({"objective", "求职意向"})
SUMMARY_EVIDENCE_SECTIONS = frozenset({"summary", "profile", "about", "个人简介"})
SKILL_EVIDENCE_SECTIONS = frozenset(
    {
        "skills",
        "专业技能",
        "技能",
        "qualifications",
        "experience",
        "工作经历",
        "projects",
        "项目经历",
        "summary",
        "profile",
        "个人简介",
    }
)

NAME_CONTEXT_REJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"推荐人",
        r"证明人",
        r"联系人",
        r"紧急联系人",
        r"\breference\b",
        r"\breferee\b",
        r"\bcontact\s+name\b",
        r"\bperson\s+who\s+can\s+vouch\s+for\s+me\b",
        r"\bvouch\s+for\b",
        r"\b(?:manager|supervisor|mentor)\s*(?:name)?\b",
        r"(?:经理|主管|导师)\s*(?:姓名|名字)",
    )
)

NAME_LABEL_PATTERNS = (
    r"姓名",
    r"候选人姓名",
    r"candidate\s+name",
    r"full\s+name",
    r"name",
)

CANDIDATE_IDENTITY_BLOCK_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:^|\n)\s*(?:candidate|applicant)\s+(?:identity|profile|information)\s*(?:$|\n)",
        r"(?:^|\n)\s*resume\s+owner\s*(?:$|[:：]|\n)",
        r"(?:^|\n)\s*(?:候选人信息|申请人信息|个人简历主体)\s*(?:$|\n)",
        r"(?:^|\n)\s*(?:candidate|applicant)\s+name\s*[:：]",
        r"(?:^|\n)\s*(?:候选人姓名|申请人姓名|简历所有者)\s*[:：]",
    )
)

NON_CANDIDATE_IDENTITY_BLOCK_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:^|\n)\s*(?:emergency\s+contact|reference|referee|contact)"
        r"(?:\s+(?:information|details|person|name))?\s*(?:$|[:：]|\n)",
        r"(?:^|\n)\s*(?:紧急联系人|推荐人|证明人|联系人)(?:信息|详情|姓名)?\s*(?:$|[:：]|\n)",
        r"(?:^|\n)\s*(?:relationship|spouse|guardian|emergency)\s*[:：]",
        r"(?:^|\n)\s*(?:关系|配偶|监护人|紧急关系)\s*[:：]",
    )
)

TARGET_ROLE_LABEL_PATTERNS = (
    r"target\s+role",
    r"目标岗位",
    r"求职方向",
)

OBJECTIVE_HEADING_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^(?:career\s+)?objective$",
        r"^(?:求职目标|求职意向)$",
    )
)

SKILL_REQUIREMENT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"技术栈要求",
        r"要求",
        r"需要",
        r"需求",
        r"\brequired\b",
        r"\brequirements?\b",
        r"\bmust[ -]?have\b",
        r"\btech(?:nology)?\s+stack\s+required\b",
        r"\b(?:preferred|expected|required)\s+(?:tech\s+)?stack\b",
        r"\b(?:ideal|desired|recommended|preferred|expected)\b",
        r"招聘需求",
    )
)

SKILL_OWNERSHIP_PREDICATE = re.compile(
    r"\b(?:owner\s*[:=]|owned\s+by|responsible\s+party\s*[:=]?|"
    r"maintained\s+by|developed\s+by|provided\s+by|by)\s+"
    r"(?!\d+(?:\.\d+)?%?\b)(?!using\b|leveraging\b)"
    r"(?P<owner>[^\n,.;:]{1,80})",
    re.IGNORECASE,
)

CHINESE_SKILL_OWNERSHIP_PREDICATE = re.compile(
    r"(?:所有者|负责人|责任方|维护方|提供方)\s*[:：]\s*"
    r"(?P<owner>[^，。；;\n]{1,40})|"
    r"(?:由|被)\s*(?P<passive_owner>[^，。；;\n]{1,30})"
    r"(?:开发|构建|实现|使用|完成|负责)",
    re.IGNORECASE,
)

CANDIDATE_OWNER_PATTERN = re.compile(
    r"^(?:the\s+)?(?:candidate|applicant|resume\s+owner|self|me|myself)$|"
    r"^(?:候选人|申请人|简历所有者|本人|自己)$",
    re.IGNORECASE,
)

CANDIDATE_SKILL_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:^|\n)\s*(?:[-*•]\s*)?(?:(?:I|candidate|applicant)\s+)?"
        r"(?:developed|built|used|implemented|designed|worked\s+with)\b",
        r"(?:^|\n)\s*(?:[-*•]\s*)?"
        r"(?:experienced|proficient|skilled|familiar)\s+(?:in|with)\b",
        r"(?:^|\n)\s*(?:[-*•]\s*)?(?:本人|我)?"
        r"(?:熟悉|掌握|擅长|使用|开发|构建|实现|设计)",
    )
)

SUMMARY_UNTRUSTED_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:prompt|system message|assistant message|instructions?)\b",
        r"(?:提示词|系统消息|模型指令|下游指令)",
        r"\b(?:downstream|subsequent)\b.{0,40}\b(?:process|profile|model|agent)\b",
        r"\b(?:output|return|emit|generate|rewrite|insert|force)\b.{0,40}"
        r"\b(?:profile|summary|result|json|field|skill)\b",
        r"(?:输出|返回|生成|改写|写入|强制).{0,40}(?:资料|档案|简介|结果|字段|技能)",
        r"\b(?:send|upload|post)\b.{0,32}\b(?:message|email|data|server)\b",
        r"\bapply\b.{0,24}\b(?:job|position)\b",
        r"\b(?:call|execute|invoke)\b.{0,24}\b(?:tool|function|command)\b",
        r"(?:发送|上传|外传).{0,32}(?:消息|邮件|数据|服务器)",
        r"(?:投递|申请).{0,24}(?:岗位|职位)",
        r"(?:调用|执行).{0,24}(?:工具|函数|命令)",
        r"\b(?:for\s+the\s+)?next\s+(?:stage|step|phase)\b",
        r"\b(?:regard|consider|assume|remember|ensure|pretend|interpret)\b.{0,48}",
        r"\b(?:model|assistant|system)\b.{0,48}\b(?:must|should|will|shall)\b",
        r"(?:下一阶段|下一步|后续阶段|后续流程).{0,48}",
        r"(?:模型|助手|系统).{0,48}(?:必须|应当|需要|执行)",
        r"\b(?:make|mark|set|classify|designate|change|modify|promote|elevate|upgrade)\b.{0,48}"
        r"\b(?:skill|profile|summary|candidate|verified)\b",
        r"\b(?:obey|follow)\b.{0,48}\b(?:instruction|command|prompt|text)\b",
        r"(?:设为|标记为|归类为|修改|更改).{0,48}(?:技能|资料|简介|候选人|已验证)",
    )
)

SUMMARY_ACTIONS = {
    "built": "Built",
    "developed": "Developed",
    "designed": "Designed",
    "implemented": "Implemented",
    "created": "Created",
    "delivered": "Delivered",
    "managed": "Managed",
}

SUMMARY_ACTION_OBJECT_PATTERN = re.compile(
    r"^(?P<action>built|developed|designed|implemented|created|delivered|managed)"
    r"\s+(?P<object>.+?)[.。]?$",
    re.IGNORECASE,
)

NOUN_PHRASE_PATTERN = re.compile(
    r"^[\w+#./-]+(?:\s+[\w+#./-]+){0,5}$",
    re.UNICODE,
)

CONTROLLED_SKILLS = {
    "python": "Python",
    "fastapi": "FastAPI",
    "docker": "Docker",
    "react": "React",
    "langchain": "LangChain",
    "pytorch": "PyTorch",
    "postgresql": "PostgreSQL",
    "rag": "RAG",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "machine learning": "Machine Learning",
    "natural language processing": "Natural Language Processing",
}

NAME_NON_NAME_TERMS = frozenset(CONTROLLED_SKILLS) | frozenset(
    {
        "build", "built", "develop", "developed", "design", "implemented",
        "create", "deliver", "manage", "use", "prioritize", "trust", "output",
        "return", "include", "ignore", "profile", "skill", "verified",
        "candidate", "applicant", "resume", "owner", "name",
    }
)

ROLE_HEADS = frozenset(
    {
        "engineer", "developer", "manager", "analyst", "designer", "architect",
        "consultant", "scientist", "specialist", "administrator", "director",
        "工程师", "开发工程师", "经理", "分析师", "设计师", "架构师", "顾问",
        "科学家", "专家", "管理员", "总监",
    }
)

ROLE_MODIFIERS = frozenset(
    {
        "backend", "frontend", "full", "stack", "software", "platform", "data",
        "machine", "learning", "ai", "ml", "devops", "cloud", "security",
        "product", "project", "engineering", "technical", "senior", "junior",
        "staff", "principal", "lead", "mobile", "web", "qa", "test", "database",
        "systems", "site", "reliability", "solutions", "后端", "前端", "全栈",
        "软件", "平台", "数据", "机器学习", "人工智能", "云", "安全", "产品",
        "项目", "高级", "初级", "资深", "移动端", "测试", "数据库", "系统",
    }
)

ENGINEERING_COMPONENT_HEADS = frozenset(
    {
        "api", "apis", "backend", "frontend", "pipeline", "service", "services",
        "system", "systems", "platform", "application", "app", "model", "database",
        "infrastructure", "workflow", "integration", "engine", "component", "module",
        "dashboard", "project", "projects",
    }
)

PROJECT_OBJECT_MODIFIERS = frozenset(
    {
        "reliable", "scalable", "distributed", "secure", "cloud", "data", "web",
        "mobile", "backend", "frontend", "production", "retrieval", "recommendation",
        "analytics", "automation",
    }
)


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).casefold()


def _value_follows_label(
    context: str,
    value: str,
    label_patterns: tuple[str, ...],
) -> bool:
    normalized_context = unicodedata.normalize("NFKC", context)
    normalized_value = unicodedata.normalize("NFKC", value).strip()
    if not normalized_value:
        return False
    value_pattern = re.escape(normalized_value).replace(r"\ ", r"\s+")
    labels = "|".join(label_patterns)
    return bool(
        re.search(
            rf"(?:^|[\n。.!?；;|])\s*(?:{labels})\s*"
            rf"(?:[:：\-–—]\s*|\s+){value_pattern}"
            rf"(?=$|[\n。.!?,，；;|])",
            normalized_context,
            re.IGNORECASE,
        )
    )


def _contains_explicit_skill(content: str, skill: str) -> bool:
    """Require a model-proposed skill to occur as a complete source term."""
    haystack = _normalized_text(content)
    needle = _normalized_text(skill)
    if not needle:
        return False
    start = 0
    while (index := haystack.find(needle, start)) >= 0:
        end = index + len(needle)
        left_ok = (
            not (needle[0].isalnum() or needle[0] == "_")
            or index == 0
            or not (haystack[index - 1].isalnum() or haystack[index - 1] == "_")
        )
        right_ok = (
            not (needle[-1].isalnum() or needle[-1] == "_")
            or end == len(haystack)
            or not (haystack[end].isalnum() or haystack[end] == "_")
        )
        if left_ok and right_ok:
            return True
        start = index + 1
    return False


def _is_instruction_line(line: str) -> bool:
    return contains_untrusted_command(line) or any(
        pattern.search(line) for pattern in PROFILE_INSTRUCTION_PATTERNS
    )


def _is_negated_skill_line(line: str) -> bool:
    return any(pattern.search(line) for pattern in NEGATED_SKILL_PATTERNS)


def _has_rejected_name_context(line: str) -> bool:
    return any(pattern.search(line) for pattern in NAME_CONTEXT_REJECTION_PATTERNS)


def _is_skill_requirement_line(line: str) -> bool:
    return any(pattern.search(line) for pattern in SKILL_REQUIREMENT_PATTERNS)


def _is_untrusted_summary_line(line: str) -> bool:
    return _is_instruction_line(line) or any(
        pattern.search(line) for pattern in SUMMARY_UNTRUSTED_PATTERNS
    )


def _noun_phrase_tokens(value: str) -> list[str] | None:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized or not NOUN_PHRASE_PATTERN.fullmatch(normalized):
        return None
    return [token.casefold() for token in normalized.split()]


def _validated_name(value: str) -> str | None:
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()
    if re.fullmatch(r"[\u3400-\u9fff]{2,4}", normalized):
        return normalized
    tokens = normalized.split()
    if not 2 <= len(tokens) <= 4:
        return None
    if any(
        not re.fullmatch(r"[A-Z][a-z]{1,30}", token)
        or token.casefold() in NAME_NON_NAME_TERMS
        for token in tokens
    ):
        return None
    return normalized


def _validated_target_role(value: str) -> str | None:
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()
    tokens = normalized.split()
    if not normalized or len(tokens) > 5:
        return None
    if len(tokens) == 1 and re.fullmatch(r"[\u3400-\u9fff]+", normalized):
        for head in sorted(ROLE_HEADS, key=len, reverse=True):
            if normalized.endswith(head):
                modifier = normalized[: -len(head)]
                if not modifier or modifier in ROLE_MODIFIERS:
                    return normalized
        return None
    folded = [token.casefold() for token in tokens]
    if folded[-1] not in ROLE_HEADS or any(
        modifier not in ROLE_MODIFIERS for modifier in folded[:-1]
    ):
        return None
    return normalized


def _controlled_skill(value: str) -> str | None:
    normalized = _normalized_text(value)
    return CONTROLLED_SKILLS.get(normalized)


def _validated_summary_object(value: str) -> str | None:
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()
    if not normalized or len(normalized) > 120:
        return None
    tokens = _noun_phrase_tokens(normalized)
    if tokens is None:
        return None
    controlled_entity = CONTROLLED_SKILLS.get(" ".join(tokens))
    if controlled_entity is not None:
        return controlled_entity
    if tokens[-1] not in ENGINEERING_COMPONENT_HEADS:
        return None
    prefix_tokens = tokens[:-1]
    prefix = " ".join(prefix_tokens)
    if prefix_tokens and prefix not in CONTROLLED_SKILLS:
        single_token_skills = {
            skill for skill in CONTROLLED_SKILLS if " " not in skill
        }
        if any(
            token not in PROJECT_OBJECT_MODIFIERS
            and token not in single_token_skills
            for token in prefix_tokens
        ):
            return None
    return normalized


def _parse_summary_action_object(line: str) -> str | None:
    match = SUMMARY_ACTION_OBJECT_PATTERN.fullmatch(line.strip())
    if match is None:
        return None
    object_value = _validated_summary_object(match.group("object"))
    if object_value is None:
        return None
    action = SUMMARY_ACTIONS[match.group("action").casefold()]
    return f"{action} {object_value}"


def _is_candidate_owner(value: str) -> bool:
    owner = re.split(
        r"\b(?:using|with|who|that|and)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    return bool(CANDIDATE_OWNER_PATTERN.fullmatch(owner))


def _has_non_candidate_skill_owner(context: str) -> bool:
    for match in SKILL_OWNERSHIP_PREDICATE.finditer(context):
        if not _is_candidate_owner(match.group("owner")):
            return True
    for match in CHINESE_SKILL_OWNERSHIP_PREDICATE.finditer(context):
        owner = match.group("owner") or match.group("passive_owner") or ""
        if not _is_candidate_owner(owner):
            return True
    return False


def _is_candidate_skill_context(context: str) -> bool:
    return (
        not _has_non_candidate_skill_owner(context)
        and not _is_untrusted_summary_line(context)
        and any(
        pattern.search(context) for pattern in CANDIDATE_SKILL_PATTERNS
        )
    )


def _evidence_section_allowed(
    evidence: ProfileDraftEvidence,
    chunks_by_id: dict[uuid.UUID, DocumentChunk],
    allowed_sections: frozenset[str],
) -> bool:
    section = _normalized_text(chunks_by_id[uuid.UUID(evidence.chunk_id)].section)
    return section in allowed_sections


def parse_profile_draft(content: str) -> ProfileDraftRead:
    """Validate the model's exact evidence-bearing JSON contract."""
    try:
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise TypeError("profile draft must be an object")
        return ProfileDraftRead.model_validate(payload)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise LLMResponseFormatError("模型返回的候选人资料格式错误") from exc


def _all_evidence(draft: ProfileDraftRead) -> Iterable[ProfileDraftEvidence]:
    if draft.name is not None:
        yield draft.name.evidence
    if draft.target_role is not None:
        yield draft.target_role.evidence
    if draft.summary is not None:
        yield from draft.summary.evidence
    for skill in draft.skills:
        yield skill.evidence


def _validate_evidence_references(
    draft: ProfileDraftRead,
    chunks_by_id: dict[uuid.UUID, DocumentChunk],
) -> None:
    """Reject unknown/cross-document chunks and non-verbatim excerpts."""
    for evidence in _all_evidence(draft):
        try:
            chunk_id = uuid.UUID(evidence.chunk_id)
        except ValueError as exc:
            raise ProfileDraftEvidenceError("profile draft evidence is invalid") from exc
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None or evidence.excerpt not in chunk.content:
            raise ProfileDraftEvidenceError("profile draft evidence is invalid")


def _evidence_has_safe_context(
    evidence: ProfileDraftEvidence,
    chunks_by_id: dict[uuid.UUID, DocumentChunk],
    value: str | None = None,
) -> bool:
    chunk = chunks_by_id[uuid.UUID(evidence.chunk_id)]
    evidence_lines = [line for line in evidence.excerpt.splitlines() if line.strip()]
    if not evidence_lines or any(_is_instruction_line(line) for line in evidence_lines):
        return False
    needle = _normalized_text(value if value is not None else evidence.excerpt)
    matching_lines = [
        line
        for line in chunk.content.splitlines()
        if line.strip()
        and needle in _normalized_text(line)
    ]
    return bool(matching_lines) and any(not _is_instruction_line(line) for line in matching_lines)


def _safe_scalar_value(value: str, evidence: ProfileDraftEvidence) -> str | None:
    sanitized = sanitize_model_text(value)
    if not sanitized or redact_sensitive_text(evidence.excerpt) != evidence.excerpt:
        return None
    if _normalized_text(sanitized) not in _normalized_text(evidence.excerpt):
        return None
    return sanitized


def _name_evidence_has_candidate_context(
    name: str,
    evidence: ProfileDraftEvidence,
    chunks_by_id: dict[uuid.UUID, DocumentChunk],
) -> bool:
    if _has_rejected_name_context(evidence.excerpt):
        return False
    chunk = chunks_by_id[uuid.UUID(evidence.chunk_id)]
    if chunk.chunk_index != 0:
        return False
    lines = chunk.content.splitlines()
    identity_region = "\n".join(lines[:8])
    has_candidate_identity_block = any(
        pattern.search(identity_region)
        for pattern in CANDIDATE_IDENTITY_BLOCK_PATTERNS
    )
    if not has_candidate_identity_block or any(
        pattern.search(identity_region)
        for pattern in NON_CANDIDATE_IDENTITY_BLOCK_PATTERNS
    ):
        return False
    matching_contexts = [
        (
            index,
            "\n".join(lines[max(0, index - 3) : index + 4]),
        )
        for index, line in enumerate(lines)
        if _normalized_text(name) in _normalized_text(line)
    ]
    return bool(matching_contexts) and any(
        index <= 5
        and not _has_rejected_name_context(context)
        and not _is_instruction_line(context)
        and _value_follows_label(context, name, NAME_LABEL_PATTERNS)
        for index, context in matching_contexts
    )


def _target_role_evidence_has_goal_context(
    target_role: str,
    evidence: ProfileDraftEvidence,
    chunks_by_id: dict[uuid.UUID, DocumentChunk],
) -> bool:
    chunk = chunks_by_id[uuid.UUID(evidence.chunk_id)]
    lines = chunk.content.splitlines()
    matching_fields = [
        (index, line.strip())
        for index, line in enumerate(lines)
        if _normalized_text(target_role) in _normalized_text(line)
    ]
    return bool(matching_fields) and any(
        _value_follows_label(field_line, target_role, TARGET_ROLE_LABEL_PATTERNS)
        and not _is_instruction_line(field_line)
        and all(
            not previous.strip()
            or any(
                pattern.fullmatch(previous.strip())
                for pattern in OBJECTIVE_HEADING_PATTERNS
            )
            for previous in lines[:index]
        )
        for index, field_line in matching_fields
    )


def _summary_evidence_segments(
    evidence: ProfileDraftEvidence,
) -> list[tuple[ProfileDraftEvidence, str]]:
    """Parse source clauses into verified action/object facts and source evidence."""
    segments: list[str] = []
    for line in evidence.excerpt.splitlines():
        segments.extend(
            segment.strip()
            for segment in re.split(
                r"(?<=[。！？!?])\s*|(?<=\.)\s+|\s*[:：；;]\s*|"
                r"\s+[-—–]\s+|\s+(?i:and|then|but|while)\s+|"
                r"\s*(?:并且|然后|但是|同时)\s*",
                line,
            )
            if segment.strip()
        )
    if not segments:
        return []
    parsed_segments: list[tuple[ProfileDraftEvidence, str]] = []
    for candidate in segments:
        generated_fact = _parse_summary_action_object(candidate)
        if (
            generated_fact is None
            or _is_untrusted_summary_line(candidate)
            or redact_sensitive_text(candidate) != candidate
        ):
            return []
        parsed_segments.append(
            (
                ProfileDraftEvidence(
                    chunk_id=evidence.chunk_id,
                    excerpt=candidate,
                ),
                generated_fact,
            )
        )
    return parsed_segments


def _ground_draft(
    draft: ProfileDraftRead,
    chunks_by_id: dict[uuid.UUID, DocumentChunk],
) -> ProfileDraftRead:
    """Build the public draft only from validated, non-instruction evidence."""
    _validate_evidence_references(draft, chunks_by_id)

    grounded_name: ProfileDraftName | None = None
    if (
        draft.name is not None
        and _evidence_section_allowed(
            draft.name.evidence, chunks_by_id, NAME_EVIDENCE_SECTIONS
        )
        and _evidence_has_safe_context(
            draft.name.evidence, chunks_by_id, draft.name.value
        )
        and _name_evidence_has_candidate_context(
            draft.name.value, draft.name.evidence, chunks_by_id
        )
    ):
        value = _safe_scalar_value(draft.name.value, draft.name.evidence)
        if value is not None:
            validated_name = _validated_name(value)
            if validated_name is not None:
                grounded_name = draft.name.model_copy(update={"value": validated_name})

    grounded_role: ProfileDraftTargetRole | None = None
    if (
        draft.target_role is not None
        and _evidence_section_allowed(
            draft.target_role.evidence,
            chunks_by_id,
            TARGET_ROLE_EVIDENCE_SECTIONS,
        )
        and _evidence_has_safe_context(
            draft.target_role.evidence, chunks_by_id, draft.target_role.value
        )
        and _target_role_evidence_has_goal_context(
            draft.target_role.value,
            draft.target_role.evidence,
            chunks_by_id,
        )
    ):
        value = _safe_scalar_value(draft.target_role.value, draft.target_role.evidence)
        if value is not None:
            validated_role = _validated_target_role(value)
            if validated_role is not None:
                grounded_role = draft.target_role.model_copy(
                    update={"value": validated_role}
                )

    grounded_summary: ProfileDraftSummary | None = None
    if draft.summary is not None:
        safe_evidence: list[ProfileDraftEvidence] = []
        generated_facts: list[str] = []
        summary_length = 0
        for evidence in draft.summary.evidence:
            if not _evidence_section_allowed(
                evidence, chunks_by_id, SUMMARY_EVIDENCE_SECTIONS
            ):
                continue
            for safe_segment, generated_fact in _summary_evidence_segments(evidence):
                separator_length = 1 if safe_evidence else 0
                if summary_length + separator_length + len(generated_fact) > 4000:
                    break
                safe_evidence.append(safe_segment)
                generated_facts.append(generated_fact)
                summary_length += separator_length + len(generated_fact)
        if safe_evidence:
            grounded_summary = ProfileDraftSummary(
                value="\n".join(generated_facts),
                evidence=safe_evidence,
            )

    grounded_skills: list[ProfileDraftSkill] = []
    seen_skills: set[str] = set()
    for skill in draft.skills:
        value = sanitize_model_text(skill.value)
        controlled_value = _controlled_skill(value)
        evidence = skill.evidence
        chunk = chunks_by_id[uuid.UUID(evidence.chunk_id)]
        if not _evidence_section_allowed(
            evidence, chunks_by_id, SKILL_EVIDENCE_SECTIONS
        ):
            continue
        lines = chunk.content.splitlines()
        supporting_contexts = [
            "\n".join(lines[max(0, index - 1) : index + 2])
            for index, line in enumerate(lines)
            if _contains_explicit_skill(line, value)
        ]
        safe_supporting_contexts = [
            context
            for context in supporting_contexts
            if not _is_instruction_line(context)
            and not _is_negated_skill_line(context)
            and not _is_skill_requirement_line(context)
            and _is_candidate_skill_context(context)
        ]
        if (
            not value
            or controlled_value is None
            or redact_sensitive_text(evidence.excerpt) != evidence.excerpt
            or not _contains_explicit_skill(evidence.excerpt, value)
            or not _evidence_has_safe_context(evidence, chunks_by_id, value)
            or not safe_supporting_contexts
        ):
            continue
        key = _normalized_text(controlled_value)
        if key in seen_skills:
            continue
        seen_skills.add(key)
        grounded_skills.append(skill.model_copy(update={"value": controlled_value}))

    return ProfileDraftRead(
        name=grounded_name,
        target_role=grounded_role,
        summary=grounded_summary,
        skills=grounded_skills,
    )


class ProfileDraftService:
    """Apply ownership, readiness, prompt, and evidence boundaries to draft extraction."""

    def __init__(
        self,
        session: Session,
        user_email: str,
        provider: ProfileDraftProvider,
    ) -> None:
        self.session = session
        self.user_email = user_email.strip().lower()
        self.provider = provider
        self.users = UserRepository(session)
        self.documents = DocumentRepository(session)

    def generate(self, document_id: uuid.UUID) -> ProfileDraftRead:
        user = self.users.get_or_create_by_email(self.user_email)
        document = self.documents.get_for_user(document_id, user.id)
        if document is None:
            self.session.rollback()
            raise ResourceNotFoundError("document not found")
        if document.status != "ready":
            self.session.rollback()
            raise ResourceConflictError("document is not ready")

        chunks = self.documents.list_chunks_for_document(document.id)
        if not chunks or any(chunk.document_id != document.id for chunk in chunks):
            self.session.rollback()
            raise ProfileDraftExtractionError("document contains no usable chunks")

        model_chunks: list[dict[str, str | int]] = []
        remaining = MAX_PROFILE_DRAFT_INPUT_CHARS
        for chunk in chunks:
            if remaining <= 0:
                break
            content = redact_sensitive_text(chunk.content)[:remaining]
            if not content:
                continue
            model_chunks.append(
                {
                    "chunk_id": str(chunk.id),
                    "section": redact_sensitive_text(chunk.section),
                    "chunk_index": chunk.chunk_index,
                    "content": content,
                }
            )
            remaining -= len(content)
        self.session.commit()

        if not model_chunks:
            raise ProfileDraftExtractionError("document contains no usable chunks")
        raw_draft = self.provider.extract_profile_draft(model_chunks)
        draft = parse_profile_draft(raw_draft)
        return _ground_draft(draft, {chunk.id: chunk for chunk in chunks})
