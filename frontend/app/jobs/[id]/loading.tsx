import { AppShell } from "@/components/app-shell";

export default function JobDetailLoading() {
  return <AppShell><div className="animate-pulse"><div className="mb-5 h-5 w-28 rounded bg-[#e4e4e7]"/><div className="h-32 rounded-xl bg-white"/><div className="mt-5 grid gap-5 xl:grid-cols-[1.5fr_1fr]"><div className="h-96 rounded-xl bg-white"/><div className="h-64 rounded-xl bg-white"/></div></div></AppShell>;
}
