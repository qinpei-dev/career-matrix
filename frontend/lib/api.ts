import type { SecurityTestReport } from "./security-report";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const API_BASE_URL = (
  (typeof window === "undefined" ? process.env.API_BASE_URL : undefined) ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  DEFAULT_API_BASE_URL
).replace(/\/$/, "");

export interface Job {
  id: string;
  user_id: string;
  title: string;
  company: string | null;
  description: string;
  source_url: string | null;
  source_type: string;
  created_at: string;
  updated_at: string;
}

export interface JobCreateResponse extends Job {
  status: "created" | "duplicate";
  job_id: string;
  message?: string | null;
}

export interface Analysis {
  id: string;
  user_id: string;
  job_id: string;
  candidate_profile_id: string;
  status: string;
  score: number | null;
  result_json: Record<string, unknown>;
  evidence_json: AnalysisEvidence[];
  scoring_version: string | null;
  prompt_version: string | null;
  model_provider: string | null;
  model_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnalysisEvidence {
  chunk_id: string;
  document_id: string;
  content: string;
  section: string;
  requirement: string;
}

export type AnalysisTaskStatus =
  | "PENDING"
  | "FETCHING_JOB"
  | "ANALYZING"
  | "SAVING_RESULT"
  | "WAITING_FOR_REVIEW"
  | "COMPLETED"
  | "FAILED";

export interface AnalysisTaskStarted {
  task_id: string;
  status: AnalysisTaskStatus;
  current_step: string;
  progress: number;
}

export interface AnalysisTask {
  id: string;
  user_id: string;
  job_id: string;
  status: AnalysisTaskStatus;
  current_step: string;
  progress: number;
  retry_count: number;
  max_retries: number;
  error_code: string | null;
  error_message: string | null;
  result_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  is_running: boolean;
  claimed_at: string | null;
  lease_expires_at: string | null;
}

export type AgentRunStatus = "pending" | "running" | "completed" | "failed" | "timeout";
export type AgentStepStatus = "running" | "completed" | "failed";

export interface AgentRunStarted {
  run_id: string;
  status: AgentRunStatus;
}

export interface AgentStep {
  id: string;
  step_name: string;
  status: AgentStepStatus;
  input_summary: string | null;
  output_summary: string | null;
  duration_ms: number | null;
  created_at: string;
}

export interface AgentFinalResult {
  analysis_id: string;
  analysis: Record<string, unknown> & { score: number };
  evidence: AnalysisEvidence[];
}

export interface AgentRun {
  run_id: string;
  user_id: string;
  job_id: string;
  status: AgentRunStatus;
  current_step: string;
  steps: AgentStep[];
  result: AgentFinalResult | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface Profile {
  id: string;
  user_id: string;
  name: string;
  target_role: string | null;
  summary: string | null;
  skills: string[];
  created_at: string;
  updated_at: string;
}

export interface ResumeDocument {
  id: string;
  filename: string;
  file_type: "pdf" | "docx";
  status: string;
  chunk_count: number;
  created_at: string;
}

export interface ResumeDocumentDetail extends ResumeDocument {
  updated_at: string;
}

export interface ResumeDocumentUpload extends ResumeDocumentDetail {
  upload_status: "created" | "duplicate";
  is_duplicate: boolean;
  message: string;
}

export interface DocumentChunk {
  chunk_id: string;
  section: string;
  chunk_index: number;
  content: string;
}

export interface RetrievalMatch {
  chunk_id: string;
  document_id: string;
  content: string;
  section: string;
  score: number;
}

export interface DashboardStats {
  jobs: number;
  analyses: number;
  analyzed_jobs: number;
  pending_jobs: number;
  average_score: number | null;
  high_matches: number;
  documents: number;
  ready_documents: number;
  active_tasks: number;
  failed_tasks: number;
}

export interface DashboardRecentAnalysis {
  id: string;
  job_id: string;
  job_title: string;
  company: string | null;
  status: string;
  score: number | null;
  updated_at: string;
}

export interface DashboardRecentJob extends Job {
  analysis_status: string | null;
  analysis_score: number | null;
}

export interface DashboardRecentTask {
  id: string;
  job_id: string;
  job_title: string;
  status: AnalysisTaskStatus;
  progress: number;
  error_message: string | null;
  updated_at: string;
}

export interface Dashboard {
  stats: DashboardStats;
  recent_jobs: DashboardRecentJob[];
  recent_analyses: DashboardRecentAnalysis[];
  recent_tasks: DashboardRecentTask[];
}

export interface WorkspaceSearchResult {
  type: "job" | "resume" | "analysis";
  id: string;
  title: string;
  subtitle: string;
  excerpt: string;
  href: string;
  updated_at: string;
}

export interface WorkspaceSearchResponse {
  query: string;
  total: number;
  results: WorkspaceSearchResult[];
}

export interface WorkspaceNotification {
  id: string;
  level: "success" | "error" | "info";
  title: string;
  detail: string;
  href: string;
  created_at: string;
}

export interface DefaultAnalysisOptions {
  auto_run: boolean;
  require_review: boolean;
}

export interface UserSettings {
  user_id: string;
  email: string;
  display_name: string;
  target_role: string | null;
  default_analysis_options: DefaultAnalysisOptions;
  page_size: 10 | 20 | 50 | 100;
  show_technical_details: boolean;
  updated_at: string;
}

export interface ProviderStatus {
  provider: string;
  model: string;
  configured: boolean;
  credential: "已配置（已脱敏）" | "未配置";
}

export interface ProviderStatuses {
  llm: ProviderStatus;
  embedding: ProviderStatus;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly body?: unknown;

  constructor(
    message: string,
    status: number,
    body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function errorMessage(body: unknown, status: number): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return `API request failed (${status})`;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  let response: Response;

  try {
    response = await fetch(url, {
      ...init,
      cache: init.cache ?? "no-store",
      headers: {
        Accept: "application/json",
        ...init.headers,
      },
    });
  } catch (error) {
    throw new ApiError(
      error instanceof Error ? `无法连接 API：${error.message}` : "无法连接 API",
      0,
    );
  }

  if (!response.ok) {
    const body = await response.json().catch(() => undefined);
    throw new ApiError(errorMessage(body, response.status), response.status, body);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  getDashboard: () => apiFetch<Dashboard>("/api/v1/workspace/dashboard"),
  searchWorkspace: (query: string, limit = 30) => apiFetch<WorkspaceSearchResponse>(
    `/api/v1/workspace/search?q=${encodeURIComponent(query)}&limit=${limit}`,
  ),
  getNotifications: (limit = 10) => apiFetch<WorkspaceNotification[]>(
    `/api/v1/workspace/notifications?limit=${limit}`,
  ),
  getSettings: () => apiFetch<UserSettings>("/api/v1/workspace/settings"),
  updateSettings: (payload: Partial<Omit<UserSettings, "user_id" | "email" | "updated_at">>) => apiFetch<UserSettings>(
    "/api/v1/workspace/settings",
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  ),
  getProviderStatuses: () => apiFetch<ProviderStatuses>("/api/v1/workspace/providers"),
  createJob: (payload: Pick<Job, "title" | "company" | "description" | "source_url" | "source_type">) => apiFetch<JobCreateResponse>(
    "/api/v1/jobs",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  ),
  getJobs: () => apiFetch<Job[]>("/api/v1/jobs"),
  getJob: (id: string) => apiFetch<Job>(`/api/v1/jobs/${encodeURIComponent(id)}`),
  analyzeJob: (id: string) => apiFetch<Analysis>(
    `/api/v1/jobs/${encodeURIComponent(id)}/analyze`,
    { method: "POST" },
  ),
  getAnalyses: () => apiFetch<Analysis[]>("/api/v1/analyses"),
  createAnalysisTask: (jobId: string) => apiFetch<AnalysisTaskStarted>(
    "/api/v1/analysis-tasks",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId }),
    },
  ),
  getAnalysisTask: (taskId: string) => apiFetch<AnalysisTask>(
    `/api/v1/analysis-tasks/${encodeURIComponent(taskId)}`,
  ),
  getActiveAnalysisTask: (jobId: string) => apiFetch<AnalysisTask>(
    `/api/v1/analysis-tasks/active?job_id=${encodeURIComponent(jobId)}`,
  ),
  runAnalysisTask: (taskId: string) => apiFetch<AnalysisTask>(
    `/api/v1/analysis-tasks/${encodeURIComponent(taskId)}/run`,
    { method: "POST" },
  ),
  retryAnalysisTask: (taskId: string) => apiFetch<AnalysisTask>(
    `/api/v1/analysis-tasks/${encodeURIComponent(taskId)}/retry`,
    { method: "POST" },
  ),
  completeAnalysisTask: (taskId: string) => apiFetch<AnalysisTask>(
    `/api/v1/analysis-tasks/${encodeURIComponent(taskId)}/complete`,
    { method: "POST" },
  ),
  createAgentRun: (jobId: string) => apiFetch<AgentRunStarted>(
    "/api/v1/agent/runs",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId }),
    },
  ),
  getAgentRun: (runId: string) => apiFetch<AgentRun>(
    `/api/v1/agent/runs/${encodeURIComponent(runId)}`,
  ),
  getMyProfile: () => apiFetch<Profile>("/api/v1/profiles/me"),
  getDocuments: () => apiFetch<ResumeDocument[]>("/api/v1/documents"),
  uploadDocument: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return apiFetch<ResumeDocumentUpload>("/api/v1/documents/upload", {
      method: "POST",
      body,
    });
  },
  deleteDocument: (id: string) => apiFetch<void>(
    `/api/v1/documents/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  ),
  getDocument: (id: string) => apiFetch<ResumeDocumentDetail>(
    `/api/v1/documents/${encodeURIComponent(id)}`,
  ),
  getDocumentChunks: (id: string) => apiFetch<DocumentChunk[]>(
    `/api/v1/documents/${encodeURIComponent(id)}/chunks`,
  ),
  searchDocuments: (query: string, topK = 5) => apiFetch<RetrievalMatch[]>(
    "/api/v1/retrieval/search",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: topK }),
    },
  ),
  runUntrustedContentSecurityTest: () => apiFetch<SecurityTestReport>(
    "/api/v1/security-tests/untrusted-content",
    { method: "POST" },
  ),
};
