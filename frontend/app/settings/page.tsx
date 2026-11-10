import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/ui";
import { api } from "@/lib/api";
import { SettingsForm } from "./settings-form";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  try {
    const [settings, providers] = await Promise.all([
      api.getSettings(),
      api.getProviderStatuses(),
    ]);
    return <AppShell><div className="animate-rise">
      <PageHeading eyebrow="Local preferences" title="工作区设置" description="设置按当前本地用户保存在后端数据库；Provider 凭据始终脱敏。" />
      <SettingsForm initial={settings} />
      <section className="mt-5 rounded-xl border border-[#e4e4e7] bg-white p-5 md:p-6">
        <h2 className="text-sm font-semibold">Provider 状态</h2>
        <p className="mt-1 text-xs text-[#71717a]">这里只显示配置状态，不读取或返回完整 API Key。</p>
        <div className="mt-5 grid gap-4 md:grid-cols-2">{[
          ["LLM", providers.llm],
          ["Embedding", providers.embedding],
        ].map(([label, provider]) => {
          const status = typeof provider === "string" ? null : provider;
          if (!status) return null;
          return <article key={label as string} className="rounded-xl border border-[#e4e4e7] p-4"><div className="flex items-center justify-between gap-3"><strong className="text-xs">{label as string}</strong><span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${status.configured ? "bg-[#e4e4e7] text-[#059669]" : "bg-[#fee2e2] text-[#b91c1c]"}`}>{status.configured ? "已配置" : "未配置"}</span></div><p className="mt-3 text-xs text-[#71717a]">{status.provider}{settings.show_technical_details ? ` · ${status.model}` : ""}</p><p className="mt-1 text-[11px] text-[#71717a]">{status.credential}</p></article>;
        })}</div>
      </section>
    </div></AppShell>;
  } catch (caught) {
    return <AppShell><div className="animate-rise"><PageHeading title="工作区设置" description="加载当前用户的后端持久化设置。" /><p role="alert" className="rounded-xl border border-[#fecaca] bg-[#fafafa] px-4 py-3 text-sm text-[#b91c1c]">{caught instanceof Error ? caught.message : "设置加载失败"}</p></div></AppShell>;
  }
}
