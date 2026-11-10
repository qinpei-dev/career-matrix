import { AppShell } from "@/components/app-shell";

export default function JobsLoading() {
  return <AppShell><div className="animate-pulse"><div className="mb-7 h-20 rounded-xl bg-[#e2e8f0]"/><div className="mb-4 h-9 w-64 rounded-full bg-[#e2e8f0]"/><section className="overflow-hidden rounded-xl border border-[#e2e8f0] bg-white">{[1,2,3,4].map((item) => <div key={item} className="flex items-center gap-4 border-t border-[#e2e8f0] px-5 py-4"><div className="h-10 w-10 rounded-xl bg-[#e2e8f0]"/><div className="h-8 flex-1 rounded-lg bg-[#e2e8f0]"/></div>)}</section><p className="mt-4 text-center text-xs text-[#64748b]">正在读取岗位…</p></div></AppShell>;
}
