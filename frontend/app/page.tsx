import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Icon } from "@/components/icons";
import { JobRow, PageHeading } from "@/components/ui";
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
      .slice(0, 5)
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

    return <AppShell><div className="animate-rise">
      <PageHeading title="求职工作台" description={`已同步 ${stats.jobs} 个岗位，${stats.pending_jobs} 个岗位等待分析。`} action={<Link href="/jobs" className="rounded-xl bg-[#234e43] px-4 py-2.5 text-sm font-bold text-white">＋ 添加岗位</Link>} />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          ["岗位总数", String(stats.jobs), "实时", "briefcase", "bg-[#e7efe8] text-[#315d4f]"],
          ["平均匹配度", stats.average_score === null ? "—" : `${stats.average_score}%`, `${stats.analyzed_jobs} 个岗位已分析`, "trend", "bg-[#edf2d1] text-[#5f6f2d]"],
          ["简历知识库", `${stats.ready_documents}/${stats.documents}`, "已就绪 / 全部", "file", "bg-[#f7e9dd] text-[#8d5a35]"],
          ["活跃任务", String(stats.active_tasks), stats.failed_tasks ? `${stats.failed_tasks} 个失败` : "运行正常", "clock", "bg-[#e9e8f3] text-[#5f587d]"],
        ].map(([label, value, meta, icon, tone], i) => <article key={label} className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5" style={{ animationDelay: `${i * 50}ms` }}><div className="mb-5 flex items-start justify-between"><span className={`grid h-9 w-9 place-items-center rounded-xl ${tone}`}><Icon name={icon} className="h-[18px] w-[18px]" /></span><span className="text-[10px] font-bold text-[#7f8985]">{meta}</span></div><p className="text-[11px] font-semibold text-[#77817d]">{label}</p><p className="mt-1 text-[28px] font-semibold tracking-[-.04em]">{value}</p></article>)}
      </section>

      <section className="mt-5 grid gap-5 xl:grid-cols-[1.6fr_1fr]">
        <article className="soft-shadow overflow-hidden rounded-2xl border border-[#e4e9e2] bg-white">
          <div className="flex items-center justify-between px-5 py-5"><div><h2 className="text-[15px] font-bold">最近岗位</h2><p className="mt-1 text-xs text-[#89928e]">按最近更新时间排序</p></div><Link href="/jobs" className="flex items-center gap-2 text-xs font-bold text-[#315d4f]">查看全部 <Icon name="arrow" className="h-3.5 w-3.5" /></Link></div>
          {recentJobs.length > 0 && <div className="hidden grid-cols-[minmax(260px,1.3fr)_1fr_110px_100px_24px] px-5 pb-2 text-[9px] font-black uppercase tracking-[.12em] text-[#9aa29f] md:grid"><span>岗位</span><span>状态</span><span>匹配度</span><span>更新时间</span><span /></div>}
          {recentJobs.map((job) => <JobRow key={job.id} job={job}/>)}
          {recentJobs.length === 0 && <div className="border-t border-[#edf0eb] px-5 py-12 text-center"><p className="text-sm font-bold text-[#52605a]">还没有岗位</p><p className="mt-2 text-xs text-[#89928e]">添加或从浏览器扩展同步岗位后，会显示在这里。</p></div>}
        </article>

        <article className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-[#234e43] p-5 text-white">
          <div className="flex items-center justify-between"><div><h2 className="text-[15px] font-bold">分析覆盖率</h2><p className="mt-1 text-xs text-white/55">基于已保存岗位与最新分析</p></div><span className="grid h-9 w-9 place-items-center rounded-xl bg-white/10 text-[#d9ef84]"><Icon name="file" className="h-[18px] w-[18px]" /></span></div>
          <div className="my-6 flex items-end justify-between"><div><span className="text-4xl font-semibold tracking-[-.06em]">{coverage}</span><span className="ml-1 text-sm text-white/50">%</span></div><span className="rounded-full bg-[#d9ef84] px-2.5 py-1 text-[10px] font-black text-[#234e43]">{stats.analyzed_jobs} / {stats.jobs}</span></div>
          <div className="h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-[#d9ef84]" style={{ width: `${coverage}%` }}/></div>
          <p className="mt-5 text-xs leading-6 text-white/65">匹配分数、简历状态和任务进度均来自后端持久化数据。</p>
          <Link href="/resumes" className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-white/10 py-2.5 text-xs font-bold transition hover:bg-white/15">查看简历知识库 <Icon name="arrow" className="h-3.5 w-3.5" /></Link>
        </article>
      </section>

      <section className="mt-5 grid gap-5 xl:grid-cols-2">
        <article className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5"><div className="flex items-center justify-between"><div><h2 className="text-[15px] font-bold">最近分析</h2><p className="mt-1 text-xs text-[#89928e]">最近更新的真实分析结果</p></div><Link href="/jobs" className="text-xs font-bold text-[#315d4f]">选择岗位</Link></div><div className="mt-4 space-y-2">{dashboard.recent_analyses.map((analysis) => <Link key={analysis.id} href={`/jobs/${analysis.job_id}`} className="flex items-center justify-between gap-4 rounded-xl border border-[#edf0eb] p-3 hover:bg-[#f8faf7]"><div className="min-w-0"><p className="truncate text-xs font-bold">{analysis.job_title}</p><p className="mt-1 truncate text-[10px] text-[#7f8985]">{analysis.company || "未填写公司"} · {analysis.status}</p></div><strong className="text-sm text-[#315d4f]">{analysis.score === null ? "—" : analysis.score}</strong></Link>)}{dashboard.recent_analyses.length === 0 && <p className="py-8 text-center text-xs text-[#7f8985]">完成岗位分析后，结果会显示在这里。</p>}</div></article>

        <article className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5"><div className="flex items-center justify-between"><div><h2 className="text-[15px] font-bold">分析任务状态</h2><p className="mt-1 text-xs text-[#89928e]">受控工作流的最近持久化状态</p></div><Link href="/agents" className="text-xs font-bold text-[#315d4f]">工作流说明</Link></div><div className="mt-4 space-y-2">{dashboard.recent_tasks.map((task) => <Link key={task.id} href={`/jobs/${task.job_id}`} className="block rounded-xl border border-[#edf0eb] p-3 hover:bg-[#f8faf7]"><div className="flex items-center justify-between gap-4"><p className="truncate text-xs font-bold">{task.job_title}</p><span className={`shrink-0 rounded-full px-2 py-1 text-[9px] font-bold ${task.status === "FAILED" ? "bg-[#fbe8e5] text-[#a14d42]" : "bg-[#e7f0e9] text-[#3d6c50]"}`}>{taskLabels[task.status] || task.status}</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#e7ebe5]"><div className="h-full rounded-full bg-[#6c9477]" style={{ width: `${task.progress}%` }} /></div>{settings.show_technical_details && task.error_message && <p className="mt-2 text-[10px] text-[#a14d42]">{task.error_message}</p>}</Link>)}{dashboard.recent_tasks.length === 0 && <p className="py-8 text-center text-xs text-[#7f8985]">创建分析任务后，执行进度会显示在这里。</p>}</div></article>
      </section>

      <section className="mt-5 pb-20 lg:pb-0">
        <article className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5"><div className="flex items-center justify-between"><div><h2 className="text-[15px] font-bold">求职进度</h2><p className="mt-1 text-xs text-[#89928e]">当前真实数据概览</p></div><span className="text-[10px] font-bold text-[#668176]">实时</span></div><div className="mt-7 flex h-32 items-end justify-between gap-3">{funnel.map(([label, value]) => <div key={label} className="flex h-full flex-1 flex-col items-center gap-2"><strong className="text-xs">{value}</strong><div className="flex min-h-0 w-full flex-1 items-end justify-center"><div className="w-full max-w-20 rounded-t-lg bg-[#b9cdbf]" style={{height: `${value === 0 ? 2 : Math.max(12, (value / maxFunnel) * 100)}%`, backgroundColor: label === "高匹配" ? "#d9ef84" : undefined}}/></div><span className="text-[10px] text-[#7f8985]">{label}</span></div>)}</div></article>
      </section>
    </div></AppShell>;
  } catch (caught) {
    return <AppShell><div className="animate-rise"><PageHeading title="求职工作台" description="加载真实岗位、简历与分析任务概览。" /><p role="alert" className="rounded-xl border border-[#efd4ca] bg-[#fff5f1] px-4 py-3 text-sm text-[#9a4b35]">{caught instanceof Error ? caught.message : "工作台加载失败"}</p></div></AppShell>;
  }
}
