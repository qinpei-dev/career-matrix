import {
  apiFetch,
  type AgentRun,
  type AgentRunStarted,
} from "./api";

export const agentRunsApi = {
  create: (jobId: string) => apiFetch<AgentRunStarted>(
    "/api/v1/agent/runs",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId }),
    },
  ),
  get: (runId: string) => apiFetch<AgentRun>(
    `/api/v1/agent/runs/${encodeURIComponent(runId)}`,
  ),
  getActive: (jobId: string) => apiFetch<AgentRun | undefined>(
    `/api/v1/agent/runs/active?job_id=${encodeURIComponent(jobId)}`,
  ),
};
