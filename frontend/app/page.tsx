import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Icon } from "@/components/icons";
import { JobRow, JobTableHeader, PageHeading, Score } from "@/components/ui";
import { api } from "@/lib/api";
import { toJobListItem } from "@/lib/jobs";

export const dynamic = "force-dynamic";

const taskLabels: Record<string, string> = {
  PENDING: "等待开始",
  FETCHING_JOB: "读取岗位",
  ANALYZING: "分析中",
  SAVING_RESULT: "保存结果",
  WAITING_FOR_REVIEW: "等待确认",
  COMPLETED: "已完成",
  FAILED: "失败",
};

export default async function DashboardPage() {
  try {
    const [dashboard, settings] = await Promise.all([
      api.getDashboard(),
      api.getSettings(),
    ]);
    const { stats } = dashboard;
    const recentJobs = dashboard.recent_jobs
      .slice(0, 8)
      .map((job) => toJobListItem(
        job,
        job.analysis_status
          ? { status: job.analysis_status, score: job.analysis_score }
          : undefined,
      ));
    const coverage = stats.jobs
      ? Math.round((stats.analyzed_jobs / stats.jobs) * 100)
      : 0;
    const funnel = [
      ["已保存", stats.jobs],
      ["已分析", stats.analyzed_jobs],
      ["高匹配", stats.high_matches],
      ["待分析", stats.pending_jobs],
    ] as const;
    const maxFunnel = Math.max(...funnel.map(([, value]) => value), 1);

    const card = "rounded-xl border border-[#e4e4e7] bg-white";
    const cardHead = (title: string, sub: string, link?: React.ReactNode) => <div className="flex items-center justify-between gap-3 border-b border-[#f4f4f5] px-4 py-3"><div><h2 className="text-sm font-semibold">{title}</h2><p className="mt-0.5 text-xs text-[#a1a1aa]">{sub}</p></div>{link}</div>;

    return <AppShell><div className="animate-rise">
      <PageHeading title="求职工作台" description={`已保存 ${stats.jobs} 个岗位，${stats.pending_jobs} 个等待分析。`} action={<Link href="/jobs" className="inline-flex items-center gap-1.5 rounded-lg bg-[#18181b] px-3.5 py-2 text-sm font-medium text-white hover:bg-[#27272a]"><Icon name="plus" className="h-4 w-4" />添加岗位</Link>} />

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["岗位总数", String(stats.jobs), `${stats.pending_jobs} 个待分析`, "briefcase", "text-[#52525b] bg-[#f4f4f5]"],
          ["平均匹配度", stats.average_score === null ? "—" : `${stats.average_score}`, `${stats.analyzed_jobs} 个已分析 · ${stats.high_matches} 个高匹配`, "trend", "text-[#52525b] bg-[#f4f4f5]"],
          ["简历知识库", `${stats.ready_documents}/${stats.documents}`, "已就绪 / 全部", "file", "text-[#52525b] bg-[#f4f4f5]"],
          ["活跃任务", String(stats.active_tasks), stats.failed_tasks ? `${stats.failed_tasks} 个失败` : "运行正常", "clock", "text-[#52525b] bg-[#f4f4f5]"],
        ].map(([label, value, meta, icon, tone]) => <article key={label} className={`${card} flex items-center gap-3 p-3.5`}><span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${tone}`}><Icon name={icon} className="h-[18px] w-[18px]" /></span><div className="min-w-0"><p className="text-xs text-[#71717a]">{label}</p><p className="text-xl font-semibold tabular-nums leading-7">{value}</p><p className="truncate text-[11px] text-[#a1a1aa]">{meta}</p></div></article>)}
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <article className={`${card} overflow-hidden`}>
          {cardHead("最近岗位", "按最近更新时间排序", <Link href="/jobs" className="flex items-center gap-1 text-xs font-medium text-[#18181b] hover:underline">查看全部 <Icon name="arrow" className="h-3.5 w-3.5" /></Link>)}
          {recentJobs.length > 0 && <JobTableHeader />}
          {recentJobs.map((job) => <JobRow key={job.id} job={job}/>)}
          {recentJobs.length === 0 && <div className="px-4 py-12 text-center"><p className="text-sm font-medium text-[#52525b]">还没有岗位</p><p className="mt-1 text-xs text-[#a1a1aa]">在浏览器扩展里保存岗位，或点右上角“添加岗位”。</p></div>}
        </article>

        <div className="grid content-start gap-4">
          <article className={card}>
            {cardHead("求职进度", `分析覆盖率 ${coverage}%`)}
            <div className="grid gap-2.5 p-4">{funnel.map(([label, value]) => <div key={label} className="grid grid-cols-[48px_1fr_28px] items-center gap-2 text-xs"><span className="text-[#71717a]">{label}</span><div className="h-2 overflow-hidden rounded-full bg-[#f4f4f5]"><div className="h-full rounded-full" style={{ width: `${(value / maxFunnel) * 100}%`, backgroundColor: label === "待分析" ? "#a1a1aa" : "#18181b" }}/></div><strong className="text-right tabular-nums">{value}</strong></div>)}</div>
          </article>
          <article className={card}>
            {cardHead("分析任务", "最近的执行状态", <Link href="/agents" className="text-xs font-medium text-[#18181b] hover:underline">说明</Link>)}
            <div className="divide-y divide-[#f4f4f5]">{dashboard.recent_tasks.map((task) => <Link key={task.id} href={`/jobs/${task.job_id}`} className="block px-4 py-2.5 hover:bg-[#fafafa]"><div className="flex items-center justify-between gap-3"><p className="truncate text-xs font-medium">{task.job_title}</p><span className={`shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-medium ${task.status === "FAILED" ? "bg-[#fef2f2] text-[#b91c1c]" : "bg-[#f4f4f5] text-[#3f3f46]"}`}>{taskLabels[task.status] || task.status}</span></div><div className="mt-1.5 h-1 overflow-hidden rounded-full bg-[#f4f4f5]"><div className="h-full rounded-full bg-[#18181b]" style={{ width: `${task.progress}%` }} /></div>{settings.show_technical_details && task.error_message && <p className="mt-1.5 text-[11px] text-[#b91c1c]">{task.error_message}</p>}</Link>)}{dashboard.recent_tasks.length === 0 && <p className="px-4 py-6 text-center text-xs text-[#a1a1aa]">创建分析任务后，进度会显示在这里。</p>}</div>
          </article>
        </div>
      </section>

      <section className="mt-4">
        <article className={card}>
          {cardHead("最近分析", "最近更新的分析结果", <Link href="/jobs?analysis_status=analyzed" className="text-xs font-medium text-[#18181b] hover:underline">全部已分析岗位</Link>)}
          <div className="grid divide-y divide-[#f4f4f5] md:grid-cols-2 md:divide-y-0">{dashboard.recent_analyses.map((analysis) => <Link key={analysis.id} href={`/jobs/${analysis.job_id}`} className="flex items-center justify-between gap-4 px-4 py-2.5 hover:bg-[#fafafa]"><div className="min-w-0"><p className="truncate text-sm font-medium">{analysis.job_title}</p><p className="mt-0.5 truncate text-xs text-[#71717a]">{analysis.company || "未填写公司"}</p></div><Score value={analysis.score} /></Link>)}{dashboard.recent_analyses.length === 0 && <p className="px-4 py-6 text-center text-xs text-[#a1a1aa] md:col-span-2">完成岗位分析后，结果会显示在这里。</p>}</div>
        </article>
      </section>
    </div></AppShell>;
  } catch (caught) {
    return <AppShell><div className="animate-rise"><PageHeading title="求职工作台" description="加载真实岗位、简历与分析任务概览。" /><p role="alert" className="rounded-xl border border-[#fecaca] bg-[#fafafa] px-4 py-3 text-sm text-[#b91c1c]">{caught instanceof Error ? caught.message : "工作台加载失败"}</p></div></AppShell>;
  }
}
