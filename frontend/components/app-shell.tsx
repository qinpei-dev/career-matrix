"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { api, UserSettings, WorkspaceNotification } from "@/lib/api";
import { Icon } from "./icons";

const nav = [
  { href: "/", label: "工作台", icon: "grid" },
  { href: "/jobs", label: "岗位管理", icon: "briefcase" },
  { href: "/resumes", label: "简历管理", icon: "file" },
  { href: "/profile", label: "候选人资料", icon: "check" },
  { href: "/agents", label: "Agent 工作流", icon: "spark" },
];

const footerNav = [
  { href: "/settings", label: "设置", icon: "settings" },
  { href: "/security-tests/untrusted-content", label: "安全测试", icon: "spark" },
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

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <div className="min-h-screen md:grid md:grid-cols-[208px_1fr]">
      <aside className="hidden border-r border-[#e2e8f0] bg-white md:sticky md:top-0 md:flex md:h-screen md:flex-col md:px-3 md:py-4">
        <Link href="/" className="flex items-center gap-2.5 px-2.5 py-1.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-[#2563eb] text-white"><Icon name="spark" className="h-[18px] w-[18px]" /></span>
          <strong className="text-[15px] tracking-[-.01em]">CareerMatrix</strong>
        </Link>
        <nav className="mt-6 grid gap-0.5">
          {nav.map((item) => (
            <Link key={item.href} href={item.href} className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition ${isActive(item.href) ? "bg-[#eff6ff] text-[#1d4ed8]" : "text-[#475569] hover:bg-[#f1f5f9] hover:text-[#0f172a]"}`}>
              <Icon name={item.icon} className="h-4 w-4" />{item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto grid gap-0.5 border-t border-[#f1f5f9] pt-3">
          {footerNav.map((item) => (
            <Link key={item.href} href={item.href} className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition ${isActive(item.href) ? "bg-[#eff6ff] text-[#1d4ed8]" : "text-[#64748b] hover:bg-[#f1f5f9] hover:text-[#0f172a]"}`}>
              <Icon name={item.icon} className="h-4 w-4" />{item.label}
            </Link>
          ))}
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-20 border-b border-[#e2e8f0] bg-white/90 backdrop-blur">
          <div className="flex h-14 items-center gap-3 px-4 md:px-6">
            <Link href="/" className="flex items-center gap-2 md:hidden">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-[#2563eb] text-white"><Icon name="spark" className="h-4 w-4" /></span>
              <strong className="text-sm">CareerMatrix</strong>
            </Link>
            <form onSubmit={submitSearch} className="relative hidden w-full max-w-[320px] sm:block"><Icon name="search" className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#94a3b8]" /><input value={query} onChange={(event) => setQuery(event.target.value)} aria-label="搜索岗位、简历和分析结果" maxLength={200} className="w-full rounded-lg border border-[#e2e8f0] bg-[#f8fafc] py-2 pl-9 pr-3 text-sm placeholder:text-[#94a3b8]" placeholder="搜索岗位、简历和分析结果" /></form>
            <div className="relative ml-auto flex items-center gap-2">
              <button type="button" onClick={() => setNotificationsOpen((open) => !open)} title="任务通知" aria-label={`任务通知，${notifications.length} 条`} aria-expanded={notificationsOpen} className="relative grid h-9 w-9 place-items-center rounded-lg text-[#64748b] hover:bg-[#f1f5f9]"><Icon name="bell" className="h-[18px] w-[18px]" />{notifications.length > 0 && <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-[#dc2626]" />}</button>
              {notificationsOpen && <section className="absolute right-0 top-11 z-30 w-[min(360px,calc(100vw-2rem))] overflow-hidden rounded-xl border border-[#e2e8f0] bg-white shadow-xl"><div className="border-b border-[#e2e8f0] px-4 py-3"><p className="text-sm font-semibold">任务状态</p><p className="mt-0.5 text-[11px] text-[#64748b]">来自分析任务与简历处理记录</p></div>{notificationError && <p className="px-4 py-5 text-xs text-[#b91c1c]">{notificationError}</p>}{!notificationError && notifications.length === 0 && <p className="px-4 py-6 text-center text-xs text-[#64748b]">暂无完成或失败的任务</p>}<div className="max-h-80 overflow-y-auto">{notifications.map((item) => <Link key={item.id} href={item.href} onClick={() => setNotificationsOpen(false)} className="block border-b border-[#f1f5f9] px-4 py-3 last:border-0 hover:bg-[#f8fafc]"><div className="flex items-start justify-between gap-3"><p className={`text-xs font-semibold ${item.level === "error" ? "text-[#b91c1c]" : "text-[#1d4ed8]"}`}>{item.title}</p><time className="shrink-0 text-[10px] text-[#94a3b8]">{new Date(item.created_at).toLocaleDateString("zh-CN")}</time></div><p className="mt-1 line-clamp-2 text-xs text-[#64748b]">{item.detail}</p></Link>)}</div></section>}
              <Link href="/settings" className="flex items-center gap-2 rounded-lg py-1 pl-1 pr-2 hover:bg-[#f1f5f9]"><span className="grid h-8 w-8 place-items-center rounded-full bg-[#dbeafe] text-xs font-bold text-[#1d4ed8]">{initials || "…"}</span><div className="hidden sm:block"><p className="max-w-32 truncate text-xs font-semibold">{settings?.display_name || "载入用户设置"}</p><p className="max-w-32 truncate text-[11px] text-[#64748b]">{settings?.target_role || settings?.email || "本地工作区"}</p></div></Link>
            </div>
          </div>
          <nav aria-label="主菜单" className="flex gap-1 overflow-x-auto px-3 pb-2 md:hidden">
            {[...nav, ...footerNav].map((item) => (
              <Link key={item.href} href={item.href} className={`shrink-0 rounded-lg px-3 py-1.5 text-[13px] font-medium ${isActive(item.href) ? "bg-[#eff6ff] text-[#1d4ed8]" : "text-[#475569]"}`}>{item.label}</Link>
            ))}
          </nav>
        </header>
        <main className="mx-auto max-w-[1280px] px-4 py-5 md:px-6 md:py-6">{children}</main>
      </div>
    </div>
  );
}
