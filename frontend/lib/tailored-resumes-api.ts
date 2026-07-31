import { API_BASE_URL, apiFetch } from "./api.ts";

export type TailoredResumeStatus =
  | "DRAFT"
  | "GENERATED"
  | "EDITING"
  | "FINALIZED"
  | "FAILED";

export interface TailoredItem {
  text: string;
  evidence_ids: string[];
  action: "保留" | "改写" | "调整顺序" | "删除冗余" | "缺失" | "风险";
}

export interface TailoredEvidence {
  id: string;
  source_type: "resume_chunk";
  source_id: string;
  document_id: string;
  section: string;
  content: string;
  rag_score: number | null;
}

export interface TailoredWarning {
  code: string;
  keyword?: string;
  message: string;
  action: "缺失" | "风险";
}

export interface TailoredResume {
  id: string;
  user_id: string;
  job_id: string;
  source_document_id: string;
  title: string;
  status: TailoredResumeStatus;
  summary: string;
  skills_json: string[];
  experience_json: TailoredItem[];
  projects_json: TailoredItem[];
  education_json: TailoredItem[];
  evidence_json: TailoredEvidence[];
  warnings_json: TailoredWarning[];
  generated_content_json: {
    original?: {
      summary?: string;
      skills?: string[];
      experience?: string[];
      projects?: string[];
    };
    keyword_coverage?: { covered?: string[]; missing?: string[] };
    generation_policy?: string;
    no_external_actions?: boolean;
  };
  user_edited_content_json: Record<string, unknown>;
  error_message: string | null;
  is_generating: boolean;
  version: number;
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TailoredResumeListItem {
  id: string;
  job_id: string;
  source_document_id: string;
  title: string;
  status: TailoredResumeStatus;
  warnings_json: TailoredWarning[];
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TailoredResumeUpdate {
  summary?: string;
  skills?: string[];
  experience?: TailoredItem[];
  projects?: TailoredItem[];
  education?: TailoredItem[];
}

export function canGenerate(status: TailoredResumeStatus, busy: boolean): boolean {
  return !busy && (status === "DRAFT" || status === "FAILED" || status === "FINALIZED");
}

export function comparisonLabel(
  original: string,
  tailored: string,
): "保留" | "改写" | "调整顺序" | "删除冗余" {
  if (original === tailored) return "保留";
  if (!tailored.trim()) return "删除冗余";
  const originalParts = original.split(/\s+/).filter(Boolean).sort().join(" ");
  const tailoredParts = tailored.split(/\s+/).filter(Boolean).sort().join(" ");
  return originalParts === tailoredParts ? "调整顺序" : "改写";
}

export const tailoredResumesApi = {
  create: (payload: { job_id: string; source_document_id: string }) =>
    apiFetch<{ tailored_resume_id: string; status: TailoredResumeStatus }>(
      "/api/v1/tailored-resumes",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    ),
  list: (jobId: string) => apiFetch<TailoredResumeListItem[]>(
    `/api/v1/tailored-resumes?job_id=${encodeURIComponent(jobId)}`,
  ),
  get: (id: string) => apiFetch<TailoredResume>(
    `/api/v1/tailored-resumes/${encodeURIComponent(id)}`,
  ),
  generate: (id: string) => apiFetch<TailoredResume>(
    `/api/v1/tailored-resumes/${encodeURIComponent(id)}/generate`,
    { method: "POST" },
  ),
  update: (id: string, payload: TailoredResumeUpdate) => apiFetch<TailoredResume>(
    `/api/v1/tailored-resumes/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  ),
  finalize: (id: string) => apiFetch<TailoredResume>(
    `/api/v1/tailored-resumes/${encodeURIComponent(id)}/finalize`,
    { method: "POST" },
  ),
  delete: (id: string) => apiFetch<void>(
    `/api/v1/tailored-resumes/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  ),
  docxUrl: (id: string) =>
    `${API_BASE_URL}/api/v1/tailored-resumes/${encodeURIComponent(id)}/export.docx`,
};
