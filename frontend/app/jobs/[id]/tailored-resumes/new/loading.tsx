import { AppShell } from "@/components/app-shell";

export default function Loading() {
  return <AppShell><div className="animate-pulse space-y-5">
    <div className="h-8 w-48 rounded bg-[#e8ece6]" />
    <div className="h-40 rounded-2xl bg-[#eef1ec]" />
    <div className="h-72 rounded-2xl bg-[#eef1ec]" />
  </div></AppShell>;
}
