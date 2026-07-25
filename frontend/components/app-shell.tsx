"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./icons";

const nav = [
  { href: "/security-tests/untrusted-content", label: "安全测试", icon: "spark" },
  { href: "/", label: "工作台", icon: "grid" },
  { href: "/jobs", label: "岗位管理", icon: "briefcase" },
  { href: "/resumes", label: "简历管理", icon: "file" },
  { href: "/agents", label: "Agent 预览", icon: "spark" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[244px_1fr]">
      <aside className="border-b border-[#dfe5dd] bg-[#eef2eb]/90 px-5 py-5 backdrop-blur lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r lg:px-4 lg:py-7">
        <div className="flex items-center justify-between lg:block">
          <Link href="/" className="flex items-center gap-3 px-2">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-[#234e43] text-[#d9ef84] shadow-lg shadow-[#234e43]/15"><Icon name="spark" /></span>
            <span><strong className="block text-[15px] tracking-[-.02em]">AI Job Copilot</strong><small className="text-[10px] font-bold tracking-[.18em] text-[#79827f]">WORKSPACE 2.0</small></span>
          </Link>
          <span className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-[#426058] ring-1 ring-[#dfe5dd] lg:hidden">Demo</span>
        </div>

        <nav className="mt-0 hidden gap-1 lg:mt-12 lg:grid">
          <p className="mb-2 px-3 text-[10px] font-bold tracking-[.16em] text-[#909994]">主菜单</p>
          {nav.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return <Link key={item.href} href={item.href} className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition ${active ? "bg-white text-[#234e43] shadow-sm" : "text-[#66706d] hover:bg-white/60 hover:text-[#234e43]"}`}><Icon name={item.icon} className="h-[18px] w-[18px]" />{item.label}{item.label === "Agent 预览" && <span className="ml-auto rounded-full bg-[#e2e6e0] px-1.5 py-0.5 text-[8px] font-black text-[#7f8985]">未来</span>}</Link>;
          })}
        </nav>

        <div className="absolute bottom-7 left-4 right-4 hidden lg:block">
          <div className="fine-grid rounded-2xl border border-[#dce3da] bg-[#f7f9f5] p-4">
            <span className="mb-3 grid h-8 w-8 place-items-center rounded-lg bg-[#e4eedf] text-[#315d4f]"><Icon name="spark" className="h-4 w-4" /></span>
            <p className="text-xs font-bold">扩展已连接</p><p className="mt-1 text-[11px] leading-5 text-[#76807c]">从浏览器采集的岗位会自动进入待评估列表。</p>
          </div>
          <button disabled title="设置功能暂未开放" className="mt-4 flex w-full cursor-not-allowed items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-[#9aa19e]"><Icon name="settings" className="h-[18px] w-[18px]" />设置（暂未开放）</button>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="flex h-[76px] items-center justify-between border-b border-[#e3e8e1] bg-[#f7f9f5]/80 px-5 backdrop-blur md:px-8 lg:px-10">
          <div className="relative hidden w-full max-w-[360px] sm:block"><Icon name="search" className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#a5aca9]" /><input disabled aria-label="搜索岗位（暂未开放）" className="w-full cursor-not-allowed rounded-xl border border-[#e0e6de] bg-[#f1f3f0] py-2.5 pl-10 pr-4 text-sm placeholder:text-[#9ba39f]" placeholder="搜索功能暂未开放" /></div>
          <div className="ml-auto flex items-center gap-3"><button disabled title="通知功能暂未开放" aria-label="通知（暂未开放）" className="grid h-10 w-10 cursor-not-allowed place-items-center rounded-xl border border-[#e0e6de] bg-[#f1f3f0] text-[#9aa19e]"><Icon name="bell" className="h-[18px] w-[18px]" /></button><div className="h-7 w-px bg-[#dfe4de]"/><div className="flex items-center gap-2.5"><span className="grid h-9 w-9 place-items-center rounded-full bg-[#d9ef84] text-xs font-black text-[#234e43]">LW</span><div className="hidden sm:block"><p className="text-xs font-bold">流水</p><p className="text-[10px] text-[#8a938f]">求职进行中</p></div></div></div>
        </header>
        <main className="px-5 py-7 md:px-8 lg:px-10 lg:py-9">{children}</main>
      </div>

      <nav className="fixed bottom-3 left-1/2 z-20 flex -translate-x-1/2 gap-1 rounded-2xl border border-[#dce3da] bg-white/95 p-1.5 shadow-xl backdrop-blur lg:hidden">
        {nav.map((item) => <Link key={item.href} href={item.href} aria-label={item.label} className={`grid h-10 w-12 place-items-center rounded-xl ${pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href)) ? "bg-[#234e43] text-white" : "text-[#75807b]"}`}><Icon name={item.icon} className="h-[18px] w-[18px]" /></Link>)}
      </nav>
    </div>
  );
}
