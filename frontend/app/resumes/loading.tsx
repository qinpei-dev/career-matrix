import { AppShell } from "@/components/app-shell";

export default function ProfileLoading() {
  return <AppShell><div className="animate-pulse"><div className="mb-7 h-20 rounded-xl bg-[#e4e4e7]"/><div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]"><div className="h-72 rounded-xl bg-white"/><div className="h-72 rounded-xl bg-white"/></div></div></AppShell>;
}
