import { AppShell } from "@/components/app-shell";
import { Icon } from "@/components/icons";
import { PageHeading } from "@/components/ui";
import Link from "next/link";

const capabilities = [
  ["岗位研究", "提取核心要求、公司信息与岗位风险", "search"],
  ["候选人证据匹配", "把 Profile 中的技能和经历映射到岗位要求", "check"],
  ["简历优化建议", "生成可审阅、可追溯的定制建议", "file"],
  ["面试准备", "整理高频问题、回答框架与准备清单", "clock"],
];

export default function AgentsPage(){return <AppShell><div className="animate-rise"><PageHeading eyebrow="Agent workflow" title="Career Copilot Agent 工作流" description="真实受控 Agent 已接入岗位详情页；选择一个岗位即可创建运行并查看后端持久化步骤。"/><section className="rounded-2xl bg-[#234e43] p-6 text-white md:p-7"><div className="flex flex-col justify-between gap-5 md:flex-row md:items-center"><div className="flex items-center gap-4"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-white/10 text-[#d9ef84]"><Icon name="spark"/></span><div><h2 className="text-base font-bold">真实 Agent 运行入口</h2><p className="mt-1 text-xs text-white/65">岗位详情 → 运行 Copilot Agent → 实时步骤与结果</p></div></div><Link href="/jobs" className="rounded-xl bg-[#d9ef84] px-4 py-2.5 text-xs font-bold text-[#234e43]">选择岗位运行</Link></div></section><section className="soft-shadow mt-5 rounded-2xl border border-[#e4e9e2] bg-white p-6"><div><h2 className="text-[15px] font-bold">当前工作流能力</h2><p className="mt-1 text-xs text-[#858e8a]">执行状态来自 Backend Agent Run，不使用模拟数据。</p></div><div className="mt-7 grid gap-4 md:grid-cols-2">{capabilities.map(([title, description, icon], i)=><article key={title} className="rounded-2xl border border-[#e6ebe4] p-5"><div className="flex items-start gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#eef2e9] text-[#557064]"><Icon name={icon} className="h-4 w-4"/></span><div><p className="text-xs font-bold"><span className="mr-2 text-[#91a09a]">0{i + 1}</span>{title}</p><p className="mt-2 text-[11px] leading-5 text-[#7d8783]">{description}</p></div></div></article>)}</div></section></div></AppShell>}
