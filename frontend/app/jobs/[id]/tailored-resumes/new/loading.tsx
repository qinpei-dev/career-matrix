import { AppShell } from "@/components/app-shell";

export default function Loading() {
  return <AppShell><div className="animate-pulse space-y-5">
    <div className="h-8 w-48 rounded bg-[#e2e8f0]" />
    <div className="h-40 rounded-xl bg-[#e2e8f0]" />
    <div className="h-72 rounded-xl bg-[#e2e8f0]" />
  </div></AppShell>;
}
