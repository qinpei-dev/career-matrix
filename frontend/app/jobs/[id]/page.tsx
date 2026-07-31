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
  const accent = (job.company ? company : job.title).slice(0, 2);

  return <AppShell><div className="animate-rise pb-20 lg:pb-0">
    <Link href="/jobs" className="mb-5 inline-flex items-center gap-2 text-xs font-bold text-[#65716c]">
      <span className="rotate-180"><Icon name="arrow" className="h-3.5 w-3.5" /></span>
      返回岗位管理
    </Link>
    <section className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5 md:p-7">
      <div className="flex flex-col justify-between gap-5 md:flex-row md:items-start">
        <div className="flex gap-4">
          <span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-[#edf2eb] text-sm font-black text-[#466157]">{accent.toUpperCase()}</span>
          <div>
            <h1 className="text-2xl font-semibold tracking-[-.04em]">{job.title}</h1>
            <p className="mt-2 text-sm text-[#6f7975]">{company} · 来源：{job.source_type}</p>
            {job.source_url && <a href={job.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex text-xs font-bold text-[#315d4f]">
              查看原始岗位 <Icon name="arrow" className="ml-1 h-3.5 w-3.5" />
            </a>}
          </div>
        </div>
        <JobActions job={job} />
      </div>
      <div className="mt-5 border-t border-[#edf0eb] pt-5">
        <Link
          href={`/jobs/${encodeURIComponent(job.id)}/tailored-resumes/new`}
          className="inline-flex items-center gap-2 rounded-xl bg-[#315d4f] px-4 py-3 text-sm font-bold text-white transition hover:bg-[#284d42]"
        >
          定制简历 <Icon name="arrow" className="h-4 w-4" />
        </Link>
        <p className="mt-2 text-xs text-[#7a8580]">基于原始简历与当前岗位 JD，生成可追溯、可编辑的新版本。</p>
      </div>
    </section>
    <div className="mt-5 grid gap-5 xl:grid-cols-[1.5fr_1fr]">
      <div className="space-y-5">
        <AnalysisWorkflow jobId={job.id} initialAnalysis={analysis} />
        <section className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-6">
          <h2 className="text-[15px] font-bold">岗位描述</h2>
          <p className="mt-4 whitespace-pre-line text-sm leading-7 text-[#68736e]">{job.description}</p>
        </section>
      </div>
      <aside><AgentWorkflow jobId={job.id} /></aside>
    </div>
  </div></AppShell>;
}
