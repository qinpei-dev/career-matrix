import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { JobRow, PageHeading } from "@/components/ui";
import { api } from "@/lib/api";
import { jobsApi, type JobListQuery } from "@/lib/jobs-api";
import { latestAnalysesByJob, toJobListItem } from "@/lib/jobs";
import { JobCreateForm } from "./job-create-form";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 10;

type SearchParams = {
  query?: string;
  source_type?: string;
  analysis_status?: string;
  sort?: string;
  page?: string;
  deleted?: string;
};

function pageHref(params: SearchParams, page: number): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value && key !== "page") query.set(key, value);
  }
  if (page > 1) query.set("page", String(page));
  return `/jobs${query.size ? `?${query}` : ""}`;
}

export default async function JobsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const requestedPage = Number.parseInt(params.page || "1", 10);
  const page = Number.isFinite(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const analysisStatus = ["analyzed", "pending"].includes(params.analysis_status || "")
    ? params.analysis_status as JobListQuery["analysisStatus"]
    : undefined;
  const sort = ["updated_desc", "created_desc", "title_asc", "company_asc"].includes(
    params.sort || "",
  ) ? params.sort as JobListQuery["sort"] : "updated_desc";
  const [pageJobs, analyses] = await Promise.all([
    jobsApi.list({
      query: params.query?.trim() || undefined,
      sourceType: params.source_type || undefined,
      analysisStatus,
      sort,
      offset: (page - 1) * PAGE_SIZE,
      limit: PAGE_SIZE + 1,
    }),
    api.getAnalyses(),
  ]);
  const hasNextPage = pageJobs.length > PAGE_SIZE;
  const jobs = pageJobs.slice(0, PAGE_SIZE);
  const analysisByJob = latestAnalysesByJob(analyses);
  const rows = jobs.map((job) => toJobListItem(job, analysisByJob.get(job.id)));
  const hasFilters = Boolean(params.query || params.source_type || params.analysis_status);

  return <AppShell><div className="animate-rise">
    <PageHeading
      eyebrow="Job pipeline"
      title="岗位管理"
      description="搜索、筛选并维护从浏览器扩展或手动保存的真实岗位。"
      action={<JobCreateForm />}
    />
    {params.deleted === "1" && <p role="status" className="mb-4 rounded-xl bg-[#e9f5ec] px-4 py-3 text-sm text-[#2e654c]">岗位及其历史记录已删除。</p>}
    <form action="/jobs" className="mb-4 grid gap-3 rounded-2xl border border-[#e4e9e2] bg-white p-4 md:grid-cols-[minmax(220px,1fr)_160px_160px_180px_auto]">
      <input
        name="query"
        defaultValue={params.query}
        maxLength={200}
        placeholder="搜索岗位或公司"
        className="rounded-xl border border-[#dfe5dd] px-3 py-2.5 text-sm"
      />
      <select name="source_type" defaultValue={params.source_type || ""} className="rounded-xl border border-[#dfe5dd] px-3 py-2.5 text-sm">
        <option value="">全部来源</option>
        <option value="manual">手动添加</option>
        <option value="extension">浏览器扩展</option>
      </select>
      <select name="analysis_status" defaultValue={analysisStatus || ""} className="rounded-xl border border-[#dfe5dd] px-3 py-2.5 text-sm">
        <option value="">全部状态</option>
        <option value="analyzed">已有分析</option>
        <option value="pending">待分析</option>
      </select>
      <select name="sort" defaultValue={sort} className="rounded-xl border border-[#dfe5dd] px-3 py-2.5 text-sm">
        <option value="updated_desc">最近更新</option>
        <option value="created_desc">最近添加</option>
        <option value="title_asc">岗位名称 A-Z</option>
        <option value="company_asc">公司名称 A-Z</option>
      </select>
      <button className="rounded-xl bg-[#234e43] px-4 py-2.5 text-sm font-bold text-white">应用</button>
    </form>
    {hasFilters && <div className="mb-4 flex items-center justify-between gap-3 rounded-xl bg-[#edf2eb] px-4 py-3 text-xs text-[#466157]">
      <span>已应用搜索或筛选条件</span>
      <Link href="/jobs" className="font-bold underline">清除条件</Link>
    </div>}
    <section className="soft-shadow overflow-hidden rounded-2xl border border-[#e4e9e2] bg-white">
      {rows.length > 0 && <div className="hidden grid-cols-[minmax(260px,1.3fr)_1fr_110px_100px_24px] px-5 py-4 text-[9px] font-black uppercase tracking-[.12em] text-[#9aa29f] md:grid"><span>岗位</span><span>状态</span><span>匹配度</span><span>更新时间</span><span /></div>}
      {rows.map((job) => <JobRow key={job.id} job={job} />)}
      {rows.length === 0 && <div className="px-6 py-16 text-center">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-[#edf2eb] text-[#466157]">0</span>
        <h2 className="mt-4 text-sm font-bold">{hasFilters ? "没有匹配的岗位" : "暂无岗位"}</h2>
        <p className="mt-2 text-xs text-[#858e8a]">{hasFilters ? "尝试调整搜索词或清除筛选条件。" : "添加岗位后，持久化数据会显示在这里。"}</p>
      </div>}
    </section>
    <nav aria-label="岗位分页" className="mt-5 flex items-center justify-center gap-3 pb-20 lg:pb-0">
      {page > 1
        ? <Link href={pageHref(params, page - 1)} className="rounded-xl border border-[#dfe5dd] bg-white px-4 py-2 text-xs font-bold">上一页</Link>
        : <span className="rounded-xl border border-[#edf0eb] px-4 py-2 text-xs text-[#a3aaa7]">上一页</span>}
      <span className="text-xs text-[#6f7975]">第 {page} 页</span>
      {hasNextPage
        ? <Link href={pageHref(params, page + 1)} className="rounded-xl border border-[#dfe5dd] bg-white px-4 py-2 text-xs font-bold">下一页</Link>
        : <span className="rounded-xl border border-[#edf0eb] px-4 py-2 text-xs text-[#a3aaa7]">下一页</span>}
    </nav>
  </div></AppShell>;
}
