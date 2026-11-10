"use client";

import { AppShell } from "@/components/app-shell";

export default function JobsError({ reset }: { error: Error; reset: () => void }) {
  return <AppShell><section className="rounded-xl border border-[#fecaca] bg-white px-6 py-16 text-center"><h1 className="text-lg font-semibold">岗位加载失败</h1><p className="mt-2 text-sm text-[#71717a]">请确认 FastAPI 服务和 API 地址可访问。</p><button onClick={reset} className="mt-5 rounded-xl bg-[#18181b] px-4 py-2.5 text-xs font-semibold text-white">重新加载</button></section></AppShell>;
}
