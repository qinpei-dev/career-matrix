import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Icon } from "@/components/icons";
import { PageHeading } from "@/components/ui";
import { api, WorkspaceSearchResponse } from "@/lib/api";

export const dynamic = "force-dynamic";

const typeLabels = {
  job: "岗位",
  resume: "简历",
  analysis: "分析",
} as const;

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  const query = q.trim();
  let response: WorkspaceSearchResponse | null = null;
  let error = "";

  if (query) {
    try {
      const settings = await api.getSettings();
      response = await api.searchWorkspace(query, settings.page_size);
    } catch (caught) {
      error = caught instanceof Error ? caught.message : "搜索请求失败";
    }
  }

  return <AppShell><div className="animate-rise">
    <PageHeading
      eyebrow="Workspace search"
      title="站内搜索"
      description="搜索当前用户的岗位标题与公司、简历名称以及分析结果。"
    />
    <form action="/search" className="flex gap-3 rounded-xl border border-[#e4e4e7] bg-white p-4">
      <div className="relative min-w-0 flex-1">
        <Icon name="search" className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#a1a1aa]" />
        <input name="q" defaultValue={query} required maxLength={200} autoFocus className="w-full rounded-xl border border-[#e4e4e7] py-3 pl-10 pr-4 text-sm" placeholder="输入岗位、公司、简历或分析关键词" />
      </div>
      <button className="rounded-xl bg-[#18181b] px-5 py-3 text-sm font-semibold text-white">搜索</button>
    </form>

    {error && <p role="alert" className="mt-5 rounded-xl border border-[#fecaca] bg-[#fafafa] px-4 py-3 text-sm text-[#b91c1c]">{error}</p>}
    {!query && <section className="mt-5 rounded-xl border border-[#e4e4e7] bg-white px-6 py-16 text-center"><Icon name="search" className="mx-auto h-8 w-8 text-[#71717a]" /><h2 className="mt-4 text-sm font-semibold">输入关键词开始搜索</h2><p className="mt-2 text-xs text-[#71717a]">结果均来自当前用户的后端持久化数据。</p></section>}
    {response && <section className="mt-5 overflow-hidden rounded-xl border border-[#e4e4e7] bg-white">
      <div className="flex items-center justify-between border-b border-[#e4e4e7] px-5 py-4"><p className="text-sm font-semibold">“{response.query}” 的结果</p><span className="text-xs text-[#71717a]">{response.total} 条</span></div>
      {response.results.map((item) => <Link key={`${item.type}:${item.id}`} href={item.href} className="block border-b border-[#e4e4e7] px-5 py-4 last:border-0 hover:bg-[#fafafa]">
        <div className="flex items-start justify-between gap-4"><div className="min-w-0"><span className="rounded-full bg-[#e4e4e7] px-2 py-1 text-[11px] font-semibold text-[#18181b]">{typeLabels[item.type]}</span><h2 className="mt-2 truncate text-sm font-semibold">{item.title}</h2><p className="mt-1 text-xs text-[#71717a]">{item.subtitle}</p><p className="mt-2 line-clamp-2 text-xs leading-5 text-[#71717a]">{item.excerpt}</p></div><Icon name="arrow" className="mt-6 h-4 w-4 shrink-0 text-[#a1a1aa]" /></div>
      </Link>)}
      {response.results.length === 0 && <div className="px-6 py-16 text-center"><h2 className="text-sm font-semibold">没有匹配结果</h2><p className="mt-2 text-xs text-[#71717a]">尝试公司名称、岗位关键词、简历文件名或分析结论中的文字。</p></div>}
      {response.total > response.results.length && <p className="border-t border-[#e4e4e7] px-5 py-3 text-center text-[11px] text-[#71717a]">按设置中的每页数量显示前 {response.results.length} 条结果。</p>}
    </section>}
  </div></AppShell>;
}
