"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { jobsApi, type SavedJob } from "@/lib/jobs-api";

export function JobActions({ job }: { job: SavedJob }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || deleting) return;
    const form = new FormData(event.currentTarget);
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await jobsApi.update(job.id, {
        title: String(form.get("title") || ""),
        company: String(form.get("company") || "") || null,
        source_url: String(form.get("source_url") || "") || null,
        description: String(form.get("description") || ""),
      });
      setEditing(false);
      setSuccess("岗位信息已保存。");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "岗位保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (saving || deleting) return;
    const confirmed = window.confirm(
      `确定删除“${job.title}”吗？相关的历史分析和任务记录也会删除，此操作无法撤销。`,
    );
    if (!confirmed) return;
    setDeleting(true);
    setError("");
    setSuccess("");
    try {
      await jobsApi.delete(job.id);
      router.push("/jobs?deleted=1");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "岗位删除失败");
      setDeleting(false);
    }
  }

  return <div className="w-full md:w-auto">
    <div className="flex flex-wrap justify-end gap-2">
      <button
        type="button"
        onClick={() => { setEditing((value) => !value); setError(""); setSuccess(""); }}
        disabled={saving || deleting}
        className="rounded-xl border border-[#dfe5dd] bg-white px-4 py-2.5 text-xs font-bold disabled:opacity-50"
      >
        {editing ? "取消编辑" : "编辑岗位"}
      </button>
      <button
        type="button"
        onClick={remove}
        disabled={saving || deleting}
        className="rounded-xl border border-[#e8cfc5] bg-[#fff7f3] px-4 py-2.5 text-xs font-bold text-[#9b4e37] disabled:opacity-50"
      >
        {deleting ? "删除中…" : "删除岗位"}
      </button>
    </div>
    {success && <p role="status" className="mt-3 rounded-xl bg-[#e9f5ec] px-4 py-3 text-sm text-[#2e654c]">{success}</p>}
    {error && <p role="alert" className="mt-3 rounded-xl bg-[#fff1ea] px-4 py-3 text-sm text-[#9b4e37]">{error}</p>}
    {editing && <form onSubmit={save} className="mt-4 grid gap-3 rounded-2xl border border-[#dfe5dd] bg-[#fbfcfa] p-4 md:min-w-[520px]">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-xs font-bold">岗位名称
          <input name="title" required maxLength={500} defaultValue={job.title} className="rounded-xl border border-[#dfe5dd] bg-white px-3 py-2.5 text-sm font-normal" />
        </label>
        <label className="grid gap-1 text-xs font-bold">公司
          <input name="company" maxLength={300} defaultValue={job.company || ""} className="rounded-xl border border-[#dfe5dd] bg-white px-3 py-2.5 text-sm font-normal" />
        </label>
      </div>
      <label className="grid gap-1 text-xs font-bold">岗位链接
        <input name="source_url" type="url" maxLength={2048} defaultValue={job.source_url || ""} className="rounded-xl border border-[#dfe5dd] bg-white px-3 py-2.5 text-sm font-normal" />
      </label>
      <label className="grid gap-1 text-xs font-bold">岗位描述
        <textarea name="description" required rows={8} defaultValue={job.description} className="rounded-xl border border-[#dfe5dd] bg-white px-3 py-2.5 text-sm font-normal" />
      </label>
      <button disabled={saving || deleting} className="justify-self-end rounded-xl bg-[#234e43] px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50">
        {saving ? "保存中…" : "保存修改"}
      </button>
    </form>}
  </div>;
}
