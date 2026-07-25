"""Allow-listed tool registry with typed inputs, outputs, and injected handlers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

from pydantic import BaseModel

from .schemas import (
    CalculateMatchScoreInput,
    CalculateMatchScoreOutput,
    GenerateApplicationMaterialInput,
    GenerateApplicationMaterialOutput,
    RetrieveCandidateEvidenceInput,
    RetrieveCandidateEvidenceOutput,
    SaveAnalysisResultInput,
    SaveAnalysisResultOutput,
)

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

ALLOWED_ANALYSIS_TOOL_NAMES = (
    "retrieve_candidate_evidence",
    "calculate_match_score",
    "generate_application_material",
    "save_analysis_result",
)


@dataclass(frozen=True)
class ToolDefinition(Generic[InputT, OutputT]):
    name: str
    description: str
    input_schema: type[InputT]
    output_schema: type[OutputT]
    handler: Callable[[InputT], OutputT]


class ToolRegistry:
    """Registry that exposes only explicitly registered, schema-checked tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition[BaseModel, BaseModel]] = {}

    def register(self, definition: ToolDefinition[InputT, OutputT]) -> None:
        if definition.name in self._tools:
            raise ValueError(f"tool already registered: {definition.name}")
        self._tools[definition.name] = cast(ToolDefinition[BaseModel, BaseModel], definition)

    def get(self, name: str) -> ToolDefinition[BaseModel, BaseModel]:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"tool is not allowed: {name}") from exc

    def invoke(self, name: str, payload: InputT, output_schema: type[OutputT]) -> OutputT:
        definition = self.get(name)
        if not isinstance(payload, definition.input_schema):
            raise TypeError(f"invalid input schema for tool: {name}")
        if output_schema is not definition.output_schema:
            raise TypeError(f"invalid output schema for tool: {name}")
        result = definition.handler(payload)
        return output_schema.model_validate(result)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)


def create_tool_registry(
    *,
    retrieve_handler: Callable[[RetrieveCandidateEvidenceInput], RetrieveCandidateEvidenceOutput],
    calculate_handler: Callable[[CalculateMatchScoreInput], CalculateMatchScoreOutput],
    generate_handler: Callable[[GenerateApplicationMaterialInput], GenerateApplicationMaterialOutput],
    save_handler: Callable[[SaveAnalysisResultInput], SaveAnalysisResultOutput],
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name=ALLOWED_ANALYSIS_TOOL_NAMES[0],
        description="Retrieve user-owned resume evidence for explicit job requirements.",
        input_schema=RetrieveCandidateEvidenceInput,
        output_schema=RetrieveCandidateEvidenceOutput,
        handler=retrieve_handler,
    ))
    registry.register(ToolDefinition(
        name=ALLOWED_ANALYSIS_TOOL_NAMES[1],
        description="Calculate a deterministic match score from structured evidence statuses.",
        input_schema=CalculateMatchScoreInput,
        output_schema=CalculateMatchScoreOutput,
        handler=calculate_handler,
    ))
    registry.register(ToolDefinition(
        name=ALLOWED_ANALYSIS_TOOL_NAMES[2],
        description="Generate the bounded first-version match report from validated structured data.",
        input_schema=GenerateApplicationMaterialInput,
        output_schema=GenerateApplicationMaterialOutput,
        handler=generate_handler,
    ))
    registry.register(ToolDefinition(
        name=ALLOWED_ANALYSIS_TOOL_NAMES[3],
        description="Persist a completed analysis through the injected application handler.",
        input_schema=SaveAnalysisResultInput,
        output_schema=SaveAnalysisResultOutput,
        handler=save_handler,
    ))
    return registry
