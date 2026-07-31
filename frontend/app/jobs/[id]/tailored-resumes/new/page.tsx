import Link from "next/link";
import { notFound } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { ApiError } from "@/lib/api";
import { documentsApi } from "@/lib/documents-api";
import { jobsApi } from "@/lib/jobs-api";
import { tailoredResumesApi } from "@/lib/tailored-resumes-api";
import { TailoredResumeWorkflow } from "./tailored-resume-workflow";

export const dynamic = "force-dynamic";

export default async function TailoredResumePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const job = await jobsApi.get(id).catch((error) => {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  });
  const [documents, history] = await Promise.all([
    documentsApi.list(),
    tailoredResumesApi.list(job.id),
  ]);
  const readyDocuments = documents.filter(
    (document) => document.status === "ready" && document.rag_available,
  );

  return <AppShell><div className="animate-rise pb-20 lg:pb-0">
    <Link href={`/jobs/${encodeURIComponent(job.id)}`} className="text-xs font-bold text-[#65716c]">
      ← 返回岗位详情
    </Link>
    <div className="mt-5">
      <p className="text-[10px] font-black uppercase tracking-[.16em] text-[#6c7f77]">Evidence-backed tailoring</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-[-.04em]">定制简历</h1>
      <p className="mt-3 max-w-3xl text-sm leading-7 text-[#68736e]">
        基于“{job.title}”的真实 JD 与所选原始简历生成新版本。JD 和简历均作为不可信数据处理；
        无原始证据的技能、经历与指标只会进入风险提示，不会写入简历。
      </p>
    </div>
    <TailoredResumeWorkflow
      job={job}
      documents={readyDocuments}
      initialHistory={history}
    />
  </div></AppShell>;
}
