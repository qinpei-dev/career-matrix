"""Explicit Career Copilot state machine; no model-directed routing."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from ...infrastructure.llm.parser import ExtractedAnalysis
from ...core.security import public_error_message
from . import nodes
from .schemas import AgentError, AgentRunStatus, AgentStepName, ValidatedAgentInput
from .state import CareerCopilotState
from .tools import ToolRegistry

StepStarted = Callable[[AgentStepName, str], None]
StepFinished = Callable[[AgentStepName, str, int], None]
StepFailed = Callable[[AgentStepName, str, int], None]
RunFinished = Callable[[CareerCopilotState], None]


class CareerCopilotWorkflow:
    """Run each node in a fixed order and persist every transition via callbacks."""

    def __init__(
        self,
        *,
        input_loader: Callable[[CareerCopilotState], ValidatedAgentInput],
        extractor: Callable[[str, str, str], ExtractedAnalysis],
        tools: ToolRegistry,
        step_started: StepStarted,
        step_finished: StepFinished,
        step_failed: StepFailed,
        run_finished: RunFinished,
        timeout_seconds: float,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self.input_loader = input_loader
        self.extractor = extractor
        self.tools = tools
        self.step_started = step_started
        self.step_finished = step_finished
        self.step_failed = step_failed
        self.run_finished = run_finished
        self.timeout_seconds = timeout_seconds
        self.clock = clock

    def run(self, state: CareerCopilotState) -> CareerCopilotState:
        workflow_started = self.clock()
        ordered_steps: tuple[tuple[AgentStepName, Callable[[], CareerCopilotState], str], ...] = (
            (AgentStepName.VALIDATE_INPUT, lambda: nodes.validate_input(state, self.input_loader), "job and user ownership"),
            (AgentStepName.EXTRACT_JOB_REQUIREMENTS, lambda: nodes.extract_job_requirements(state, self.extractor), "saved job description"),
            (AgentStepName.RETRIEVE_CANDIDATE_EVIDENCE, lambda: nodes.retrieve_candidate_evidence(state, self.tools), "structured requirements"),
            (AgentStepName.CALCULATE_SCORE, lambda: nodes.calculate_score(state, self.extractor, self.tools), "requirements and retrieved evidence"),
            (AgentStepName.GENERATE_ANALYSIS, lambda: nodes.generate_analysis(state, self.tools), "deterministic score and evidence statuses"),
            (AgentStepName.SAVE_RESULT, lambda: nodes.save_result(state, self.tools), "validated final analysis"),
        )
        for step_name, handler, input_summary in ordered_steps:
            state.current_step = step_name
            self.step_started(step_name, input_summary)
            started = self.clock()
            try:
                handler()
            except Exception as exc:
                duration_ms = max(0, round((self.clock() - started) * 1000))
                message = public_error_message(exc, "agent workflow failed")
                state.status = AgentRunStatus.FAILED
                state.errors.append(AgentError(step=step_name, message=message))
                self.step_failed(step_name, message, duration_ms)
                self.run_finished(state)
                return state
            now = self.clock()
            duration_ms = max(0, round((now - started) * 1000))
            if now - workflow_started >= self.timeout_seconds:
                message = f"agent run exceeded {self.timeout_seconds:g} seconds"
                state.status = AgentRunStatus.TIMEOUT
                state.errors.append(AgentError(step=step_name, message=message))
                self.step_failed(step_name, message, duration_ms)
                self.run_finished(state)
                return state
            self.step_finished(step_name, self._output_summary(step_name, state), duration_ms)

        state.current_step = AgentStepName.END
        state.status = AgentRunStatus.COMPLETED
        self.run_finished(state)
        return state

    @staticmethod
    def _output_summary(step: AgentStepName, state: CareerCopilotState) -> str:
        if step is AgentStepName.VALIDATE_INPUT:
            return "input validated"
        if step is AgentStepName.EXTRACT_JOB_REQUIREMENTS and state.job_requirements:
            value = state.job_requirements
            count = sum(len(items) for items in (
                value.core_skills, value.preferred_skills, value.project_requirements,
                value.education_requirements, value.experience_requirements,
            ))
            return f"{count} requirements extracted"
        if step is AgentStepName.RETRIEVE_CANDIDATE_EVIDENCE:
            return f"{len(state.retrieved_evidence)} evidence items retrieved"
        if step is AgentStepName.CALCULATE_SCORE and state.calculated_score:
            return f"score {state.calculated_score.score}/100 calculated"
        if step is AgentStepName.GENERATE_ANALYSIS:
            return "analysis generated"
        if step is AgentStepName.SAVE_RESULT:
            return "analysis result saved"
        return "step completed"
