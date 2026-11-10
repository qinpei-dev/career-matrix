"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { jobsApi } from "@/lib/jobs-api";

export function JobCreateForm() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [duplicateJobId, setDuplicateJobId] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSaving(true);
    setError("");
    setDuplicateJobId("");
    try {
      const job = await jobsApi.create({
        title: String(form.get("title") || ""),
        company: String(form.get("company") || "") || null,
        description: String(form.get("description") || ""),
        source_url: String(form.get("source_url") || "") || null,
        source_type: "manual",
      });
      if (job.status === "duplicate") {
        setDuplicateJobId(job.job_id);
        return;
      }
      router.push(`/jobs/${job.job_id}`);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "岗位保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return <button type="button" onClick={() => setOpen(true)} className="rounded-xl bg-[#18181b] px-4 py-2.5 text-sm font-semibold text-white">＋ 添加岗位</button>;
  }

  return <form onSubmit={submit} className="mb-5 grid gap-3 rounded-xl border border-[#e4e4e7] bg-white p-5">
    <div className="grid gap-3 md:grid-cols-2">
      <input name="title" required maxLength={500} placeholder="岗位名称" className="rounded-xl border border-[#e4e4e7] px-4 py-3 text-sm" />
      <input name="company" maxLength={300} placeholder="公司（可选）" className="rounded-xl border border-[#e4e4e7] px-4 py-3 text-sm" />
    </div>
    <input name="source_url" type="url" maxLength={2048} placeholder="岗位链接（可选）" className="rounded-xl border border-[#e4e4e7] px-4 py-3 text-sm" />
    <textarea name="description" required rows={6} placeholder="岗位描述 / JD" className="rounded-xl border border-[#e4e4e7] px-4 py-3 text-sm" />
    {error && <p role="alert" className="rounded-xl bg-[#fef2f2] px-4 py-3 text-sm text-[#b91c1c]">{error}</p>}
    {duplicateJobId && <p role="status" className="rounded-xl bg-[#fffbeb] px-4 py-3 text-sm text-[#78350f]">
      该岗位已保存。<a className="font-semibold underline" href={`/jobs/${duplicateJobId}`}>查看已有岗位</a>
    </p>}
    <div className="flex justify-end gap-2">
      <button type="button" onClick={() => setOpen(false)} disabled={saving} className="rounded-xl border border-[#e4e4e7] px-4 py-2.5 text-xs font-semibold">取消</button>
      <button disabled={saving} className="rounded-xl bg-[#18181b] px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">{saving ? "保存中…" : "保存岗位"}</button>
    </div>
  </form>;
}
