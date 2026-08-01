"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { api, UserSettings, WorkspaceNotification } from "@/lib/api";
import { Icon } from "./icons";

const nav = [
  { href: "/security-tests/untrusted-content", label: "安全测试", icon: "spark" },
  { href: "/", label: "工作台", icon: "grid" },
  { href: "/jobs", label: "岗位管理", icon: "briefcase" },
  { href: "/resumes", label: "简历管理", icon: "file" },
  { href: "/profile", label: "候选人资料", icon: "check" },
  { href: "/agents", label: "Agent 工作流", icon: "spark" },
  { href: "/settings", label: "设置", icon: "settings" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [notifications, setNotifications] = useState<WorkspaceNotification[]>([]);
  const [notificationError, setNotificationError] = useState("");
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [settings, setSettings] = useState<UserSettings | null>(null);

  useEffect(() => {
    void Promise.all([
      api.getNotifications().then(setNotifications).catch(() => {
        setNotificationError("暂时无法加载任务状态");
      }),
      api.getSettings().then(setSettings).catch(() => undefined),
    ]);
  }, [pathname]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    if (normalized) router.push(`/search?q=${encodeURIComponent(normalized)}`);
  }

  const initials = settings?.display_name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

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
            return <Link key={item.href} href={item.href} className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition ${active ? "bg-white text-[#234e43] shadow-sm" : "text-[#66706d] hover:bg-white/60 hover:text-[#234e43]"}`}><Icon name={item.icon} className="h-[18px] w-[18px]" />{item.label}</Link>;
          })}
        </nav>

        <div className="absolute bottom-7 left-4 right-4 hidden lg:block">
          <div className="fine-grid rounded-2xl border border-[#dce3da] bg-[#f7f9f5] p-4">
            <span className="mb-3 grid h-8 w-8 place-items-center rounded-lg bg-[#e4eedf] text-[#315d4f]"><Icon name="spark" className="h-4 w-4" /></span>
            <p className="text-xs font-bold">扩展已连接</p><p className="mt-1 text-[11px] leading-5 text-[#76807c]">从浏览器采集的岗位会自动进入待评估列表。</p>
          </div>
          <Link href="/settings" className="mt-4 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-[#66706d] transition hover:bg-white/60 hover:text-[#234e43]"><Icon name="settings" className="h-[18px] w-[18px]" />工作区设置</Link>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="flex h-[76px] items-center justify-between border-b border-[#e3e8e1] bg-[#f7f9f5]/80 px-5 backdrop-blur md:px-8 lg:px-10">
          <form onSubmit={submitSearch} className="relative hidden w-full max-w-[360px] sm:block"><Icon name="search" className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#a5aca9]" /><input value={query} onChange={(event) => setQuery(event.target.value)} aria-label="搜索岗位、简历和分析结果" maxLength={200} className="w-full rounded-xl border border-[#e0e6de] bg-white py-2.5 pl-10 pr-4 text-sm placeholder:text-[#9ba39f]" placeholder="搜索岗位、简历和分析结果" /></form>
          <div className="relative ml-auto flex items-center gap-3">
            <button type="button" onClick={() => setNotificationsOpen((open) => !open)} title="任务通知" aria-label={`任务通知，${notifications.length} 条`} aria-expanded={notificationsOpen} className="relative grid h-10 w-10 place-items-center rounded-xl border border-[#e0e6de] bg-white text-[#61706a]"><Icon name="bell" className="h-[18px] w-[18px]" />{notifications.length > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-[#b45138]" />}</button>
            {notificationsOpen && <section className="absolute right-0 top-12 z-30 w-[min(360px,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-[#dfe5dd] bg-white shadow-xl"><div className="border-b border-[#edf0eb] px-4 py-3"><p className="text-sm font-bold">任务状态</p><p className="mt-1 text-[10px] text-[#87908c]">来自分析任务与简历处理记录</p></div>{notificationError && <p className="px-4 py-5 text-xs text-[#a44d35]">{notificationError}</p>}{!notificationError && notifications.length === 0 && <p className="px-4 py-6 text-center text-xs text-[#7f8985]">暂无完成或失败的任务</p>}<div className="max-h-80 overflow-y-auto">{notifications.map((item) => <Link key={item.id} href={item.href} onClick={() => setNotificationsOpen(false)} className="block border-b border-[#f0f2ef] px-4 py-3 last:border-0 hover:bg-[#f7f9f5]"><div className="flex items-start justify-between gap-3"><p className={`text-xs font-bold ${item.level === "error" ? "text-[#a44d35]" : "text-[#315d4f]"}`}>{item.title}</p><time className="shrink-0 text-[9px] text-[#98a09d]">{new Date(item.created_at).toLocaleDateString("zh-CN")}</time></div><p className="mt-1 line-clamp-2 text-[11px] text-[#747e7a]">{item.detail}</p></Link>)}</div></section>}
            <div className="h-7 w-px bg-[#dfe4de]"/>
            <Link href="/settings" className="flex items-center gap-2.5"><span className="grid h-9 w-9 place-items-center rounded-full bg-[#d9ef84] text-xs font-black text-[#234e43]">{initials || "…"}</span><div className="hidden sm:block"><p className="max-w-32 truncate text-xs font-bold">{settings?.display_name || "载入用户设置"}</p><p className="max-w-32 truncate text-[10px] text-[#8a938f]">{settings?.target_role || settings?.email || "本地工作区"}</p></div></Link>
          </div>
        </header>
        <main className="px-5 py-7 md:px-8 lg:px-10 lg:py-9">{children}</main>
      </div>

      <nav className="fixed bottom-3 left-1/2 z-20 flex -translate-x-1/2 gap-1 rounded-2xl border border-[#dce3da] bg-white/95 p-1.5 shadow-xl backdrop-blur lg:hidden">
        {nav.map((item) => <Link key={item.href} href={item.href} aria-label={item.label} className={`grid h-10 w-10 place-items-center rounded-xl sm:w-12 ${pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href)) ? "bg-[#234e43] text-white" : "text-[#75807b]"}`}><Icon name={item.icon} className="h-[18px] w-[18px]" /></Link>)}
      </nav>
    </div>
  );
}
