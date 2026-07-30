import { apiFetch } from "./api.ts";

export interface SavedJob {
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

export interface JobCreateResult extends SavedJob {
  status: "created" | "duplicate";
  job_id: string;
  message?: string | null;
}

export interface JobListQuery {
  query?: string;
  sourceType?: string;
  analysisStatus?: "analyzed" | "pending";
  sort?: "updated_desc" | "created_desc" | "title_asc" | "company_asc";
  offset?: number;
  limit?: number;
}

export type JobInput = Pick<
  SavedJob,
  "title" | "company" | "description" | "source_url" | "source_type"
>;

function listQueryString(query: JobListQuery): string {
  const params = new URLSearchParams();
  if (query.query) params.set("query", query.query);
  if (query.sourceType) params.set("source_type", query.sourceType);
  if (query.analysisStatus) params.set("analysis_status", query.analysisStatus);
  if (query.sort) params.set("sort", query.sort);
  if (query.offset !== undefined) params.set("offset", String(query.offset));
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

export const jobsApi = {
  create: (payload: JobInput) =>
    apiFetch<JobCreateResult>("/api/v1/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  list: (query: JobListQuery = {}) =>
    apiFetch<SavedJob[]>(`/api/v1/jobs${listQueryString(query)}`),
  get: (id: string) =>
    apiFetch<SavedJob>(`/api/v1/jobs/${encodeURIComponent(id)}`),
  update: (id: string, payload: Partial<JobInput>) =>
    apiFetch<SavedJob>(`/api/v1/jobs/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  delete: (id: string) =>
    apiFetch<void>(`/api/v1/jobs/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
};
