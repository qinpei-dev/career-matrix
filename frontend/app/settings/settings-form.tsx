"use client";

import { FormEvent, useState } from "react";
import { api, UserSettings } from "@/lib/api";

export function SettingsForm({ initial }: { initial: UserSettings }) {
  const [settings, setSettings] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const updated = await api.updateSettings({
        display_name: settings.display_name,
        target_role: settings.target_role,
        page_size: settings.page_size,
        show_technical_details: settings.show_technical_details,
        default_analysis_options: settings.default_analysis_options,
      });
      setSettings(updated);
      setMessage("设置已保存到后端数据库。");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "保存设置失败");
    } finally {
      setSaving(false);
    }
  }

  return <form onSubmit={save} className="space-y-5">
    {message && <p role="status" className="rounded-xl bg-[#e9f5ec] px-4 py-3 text-sm text-[#2e654c]">{message}</p>}
    {error && <p role="alert" className="rounded-xl bg-[#fff1ec] px-4 py-3 text-sm text-[#a44d35]">{error}</p>}

    <section className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5 md:p-6">
      <h2 className="text-sm font-bold">默认用户信息</h2>
      <p className="mt-1 text-xs text-[#7f8985]">用于本地工作区显示；Demo 身份邮箱由请求头隔离，不在此修改。</p>
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <label className="text-xs font-bold text-[#58645f]">显示名称<input required maxLength={100} value={settings.display_name} onChange={(event) => setSettings({ ...settings, display_name: event.target.value })} className="mt-2 w-full rounded-xl border border-[#dfe5dd] px-4 py-3 text-sm font-normal" /></label>
        <label className="text-xs font-bold text-[#58645f]">目标岗位<input maxLength={200} value={settings.target_role || ""} onChange={(event) => setSettings({ ...settings, target_role: event.target.value || null })} className="mt-2 w-full rounded-xl border border-[#dfe5dd] px-4 py-3 text-sm font-normal" placeholder="例如：平台工程师" /></label>
        <label className="text-xs font-bold text-[#58645f]">Demo 用户邮箱<input readOnly value={settings.email} className="mt-2 w-full rounded-xl border border-[#e5e9e3] bg-[#f4f6f3] px-4 py-3 text-sm font-normal text-[#7f8985]" /></label>
        <label className="text-xs font-bold text-[#58645f]">每页数量<select value={settings.page_size} onChange={(event) => setSettings({ ...settings, page_size: Number(event.target.value) as UserSettings["page_size"] })} className="mt-2 w-full rounded-xl border border-[#dfe5dd] bg-white px-4 py-3 text-sm font-normal"><option value={10}>10 条</option><option value={20}>20 条</option><option value={50}>50 条</option><option value={100}>100 条</option></select></label>
      </div>
    </section>

    <section className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5 md:p-6">
      <h2 className="text-sm font-bold">默认分析选项</h2>
      <div className="mt-5 space-y-4">
        <label className="flex items-start justify-between gap-5 rounded-xl border border-[#e5e9e3] p-4"><span><strong className="block text-xs">创建任务后立即运行</strong><span className="mt-1 block text-[11px] leading-5 text-[#7f8985]">关闭后，新任务将保留在 PENDING，等待你手动继续。</span></span><input type="checkbox" checked={settings.default_analysis_options.auto_run} onChange={(event) => setSettings({ ...settings, default_analysis_options: { ...settings.default_analysis_options, auto_run: event.target.checked } })} className="mt-1 h-4 w-4 accent-[#234e43]" /></label>
        <label className="flex items-start justify-between gap-5 rounded-xl border border-[#e5e9e3] bg-[#f8faf7] p-4"><span><strong className="block text-xs">完成前需要人工确认</strong><span className="mt-1 block text-[11px] leading-5 text-[#7f8985]">这是受控工作流的安全边界，当前固定开启。</span></span><input type="checkbox" checked readOnly aria-readonly="true" className="mt-1 h-4 w-4 accent-[#234e43]" /></label>
        <label className="flex items-start justify-between gap-5 rounded-xl border border-[#e5e9e3] p-4"><span><strong className="block text-xs">显示技术详情</strong><span className="mt-1 block text-[11px] leading-5 text-[#7f8985]">展示任务错误详情与 Provider 模型名等调试信息。</span></span><input type="checkbox" checked={settings.show_technical_details} onChange={(event) => setSettings({ ...settings, show_technical_details: event.target.checked })} className="mt-1 h-4 w-4 accent-[#234e43]" /></label>
      </div>
    </section>

    <button disabled={saving} className="rounded-xl bg-[#234e43] px-5 py-3 text-sm font-bold text-white disabled:cursor-wait disabled:opacity-60">{saving ? "保存中…" : "保存设置"}</button>
  </form>;
}
