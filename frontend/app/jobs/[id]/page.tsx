import Link from "next/link";
import { notFound } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Icon } from "@/components/icons";
import { api, ApiError, type Analysis } from "@/lib/api";
import { latestAnalysesByJob } from "@/lib/jobs";
import { jobsApi } from "@/lib/jobs-api";
import { AnalysisWorkflow } from "./analysis-workflow";
import { AgentWorkflow } from "./agent-workflow";
import { JobActions } from "./job-actions";

export const dynamic = "force-dynamic";

export default async function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const job = await jobsApi.get(id).catch((error) => {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  });
  const analyses = await api.getAnalyses();
  const analysis: Analysis | undefined = latestAnalysesByJob(analyses).get(job.id);
  const company = job.company || "未填写公司";
  const listingFacts = [job.salary, job.location, job.experience, job.education]
    .filter(Boolean)
    .join(" · ");
  const accent = (job.company ? company : job.title).slice(0, 2);

  return <AppShell><div className="animate-rise">
    <Link href="/jobs" className="mb-5 inline-flex items-center gap-2 text-xs font-semibold text-[#64748b]">
      <span className="rotate-180"><Icon name="arrow" className="h-3.5 w-3.5" /></span>
      返回岗位管理
    </Link>
    <section className="rounded-xl border border-[#e2e8f0] bg-white p-5 md:p-5">
      <div className="flex flex-col justify-between gap-5 md:flex-row md:items-start">
        <div className="flex gap-4">
          <span className="grid h-14 w-14 shrink-0 place-items-center rounded-xl bg-[#e2e8f0] text-sm font-semibold text-[#2563eb]">{accent.toUpperCase()}</span>
          <div>
            <h1 className="text-2xl font-semibold tracking-[-.02em]">{job.title}</h1>
            <p className="mt-2 text-sm text-[#64748b]">{company} · 来源：{job.source_type}</p>
            {listingFacts && <p className="mt-1 text-sm font-semibold text-[#2563eb]">{listingFacts}</p>}
            {job.source_url && <a href={job.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex text-xs font-semibold text-[#2563eb]">
              查看原始岗位 <Icon name="arrow" className="ml-1 h-3.5 w-3.5" />
            </a>}
          </div>
        </div>
        <JobActions job={job} />
      </div>
      <div className="mt-5 border-t border-[#e2e8f0] pt-5">
        <Link
          href={`/jobs/${encodeURIComponent(job.id)}/tailored-resumes/new`}
          className="inline-flex items-center gap-2 rounded-xl bg-[#2563eb] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2563eb]"
        >
          定制简历 <Icon name="arrow" className="h-4 w-4" />
        </Link>
        <p className="mt-2 text-xs text-[#64748b]">基于原始简历与当前岗位 JD，生成可追溯、可编辑的新版本。</p>
      </div>
    </section>
    <div className="mt-5 grid gap-5 xl:grid-cols-[1.5fr_1fr]">
      <div className="space-y-5">
        <AnalysisWorkflow jobId={job.id} initialAnalysis={analysis} />
        <section className="rounded-xl border border-[#e2e8f0] bg-white p-6">
          <h2 className="text-[15px] font-semibold">岗位描述</h2>
          <p className="mt-4 whitespace-pre-line text-sm leading-7 text-[#64748b]">{job.description}</p>
        </section>
      </div>
      <aside><AgentWorkflow jobId={job.id} /></aside>
    </div>
  </div></AppShell>;
}
