import type { Analysis, Job } from "./api";

export interface JobListItem {
  id: string;
  company: string;
  role: string;
  status: string;
  score: number | null;
  location: string;
  date: string;
  accent: string;
}

export function latestAnalysesByJob(analyses: Analysis[]): Map<string, Analysis> {
  const latest = new Map<string, Analysis>();
  for (const analysis of analyses) {
    const current = latest.get(analysis.job_id);
    if (!current || Date.parse(analysis.created_at) > Date.parse(current.created_at)) {
      latest.set(analysis.job_id, analysis);
    }
  }
  return latest;
}

type AnalysisListStatus = Pick<Analysis, "status" | "score">;

export function analysisLabel(analysis?: AnalysisListStatus): string {
  if (!analysis) return "待分析";
  const status = analysis.status.toLowerCase();
  if (["completed", "complete", "success", "succeeded"].includes(status)) return "已分析";
  if (["pending", "queued"].includes(status)) return "等待分析";
  if (["running", "processing", "in_progress"].includes(status)) return "分析中";
  if (["failed", "error"].includes(status)) return "分析失败";
  return analysis.status;
}

export function toJobListItem(job: Job, analysis?: AnalysisListStatus): JobListItem {
  const company = job.company || "未填写公司";
  const accent = company === "未填写公司"
    ? job.title.slice(0, 2).toUpperCase()
    : company.slice(0, 2).toUpperCase();

  return {
    id: job.id,
    company,
    role: job.title,
    status: analysisLabel(analysis),
    score: analysis?.score ?? null,
    location: `来源：${job.source_type}`,
    date: new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(new Date(job.updated_at)),
    accent,
  };
}
