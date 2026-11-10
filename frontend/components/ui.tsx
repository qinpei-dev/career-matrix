import Link from "next/link";
import { Icon } from "./icons";

export function PageHeading({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description: string; action?: React.ReactNode }) {
  return <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div>{eyebrow && <p className="mb-1 text-xs font-medium text-[#64748b]">{eyebrow}</p>}<h1 className="text-[22px] font-semibold tracking-[-.02em]">{title}</h1><p className="mt-1 text-sm text-[#64748b]">{description}</p></div>{action}</div>;
}

export function PrimaryButton({ children }: { children: React.ReactNode }) { return <button className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-[#2563eb] px-3.5 py-2 text-sm font-medium text-white transition hover:bg-[#1d4ed8]"><Icon name="plus" className="h-4 w-4" />{children}</button>; }

const STATUS_TONES: Record<string, string> = {
  已分析: "bg-[#ecfdf5] text-[#047857] ring-[#a7f3d0]",
  分析完成: "bg-[#ecfdf5] text-[#047857] ring-[#a7f3d0]",
  分析中: "bg-[#eff6ff] text-[#1d4ed8] ring-[#bfdbfe]",
  "AI 正在分析": "bg-[#eff6ff] text-[#1d4ed8] ring-[#bfdbfe]",
  运行中: "bg-[#eff6ff] text-[#1d4ed8] ring-[#bfdbfe]",
  等待分析: "bg-[#fffbeb] text-[#b45309] ring-[#fde68a]",
  等待用户确认: "bg-[#fffbeb] text-[#b45309] ring-[#fde68a]",
  分析失败: "bg-[#fef2f2] text-[#b91c1c] ring-[#fecaca]",
  执行失败: "bg-[#fef2f2] text-[#b91c1c] ring-[#fecaca]",
};

export function StatusPill({ status }: { status: string }) {
  const tone = STATUS_TONES[status] || "bg-[#f8fafc] text-[#475569] ring-[#e2e8f0]";
  return <span className={`inline-flex items-center whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${tone}`}>{status}</span>;
}

export function Score({ value }: { value: number | null }) {
  if (value === null) return <span className="text-sm text-[#94a3b8]">—</span>;
  const color = value >= 80 ? "#059669" : value >= 60 ? "#2563eb" : value >= 40 ? "#d97706" : "#dc2626";
  return <div className="flex items-center gap-2"><div className="h-1.5 w-14 overflow-hidden rounded-full bg-[#f1f5f9]"><div className="h-full rounded-full" style={{ width: `${value}%`, backgroundColor: color }}/></div><strong className="w-7 text-sm tabular-nums" style={{ color }}>{value}</strong></div>;
}

export const JOB_TABLE_COLUMNS = "md:grid-cols-[minmax(240px,1.6fr)_minmax(120px,1fr)_96px_120px_64px]";

export function JobTableHeader() {
  return <div className={`hidden border-b border-[#e2e8f0] bg-[#f8fafc] px-4 py-2 text-xs font-medium text-[#64748b] md:grid ${JOB_TABLE_COLUMNS}`}><span>岗位</span><span>薪资 / 地点</span><span>状态</span><span>匹配度</span><span className="text-right">更新</span></div>;
}

export function JobRow({ job }: { job: { id: string; company: string; role: string; status: string; score: number | null; location: string; salary: string; facts: string; date: string; accent: string } }) {
  return <Link href={`/jobs/${job.id}`} className={`grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 border-b border-[#f1f5f9] px-4 py-3 transition last:border-0 hover:bg-[#f8fafc] ${JOB_TABLE_COLUMNS}`}>
    <div className="flex min-w-0 items-center gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[#f1f5f9] text-xs font-semibold text-[#475569]">{job.accent}</span><div className="min-w-0"><p className="truncate text-sm font-medium text-[#0f172a]">{job.role}</p><p className="mt-0.5 truncate text-xs text-[#64748b]">{job.company} · {job.location}</p></div></div>
    <div className="min-w-0 text-right md:text-left"><p className="truncate text-sm font-medium text-[#0f172a]">{job.salary || "—"}</p><p className="mt-0.5 hidden truncate text-xs text-[#64748b] md:block">{job.facts || "—"}</p></div>
    <div className="hidden md:block"><StatusPill status={job.status}/></div>
    <div className="hidden md:block"><Score value={job.score}/></div>
    <p className="hidden text-right text-xs text-[#94a3b8] md:block">{job.date}</p>
  </Link>;
}
