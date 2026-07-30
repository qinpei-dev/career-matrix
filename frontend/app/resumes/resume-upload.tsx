"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { documentUploadNotice } from "@/lib/document-upload";
import { uploadDocument } from "@/lib/documents-api";

export function ResumeUpload() {
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [tone, setTone] = useState<"success" | "duplicate" | "error">("success");
  const [progress, setProgress] = useState(0);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("resume") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    setUploading(true);
    setProgress(0);
    setMessage("");
    try {
      const document = await uploadDocument(file, setProgress);
      const notice = documentUploadNotice(document);
      setTone(notice.tone);
      setMessage(notice.message);
      form.reset();
      router.refresh();
    } catch (caught) {
      setTone("error");
      setMessage(caught instanceof Error ? caught.message : "简历上传失败");
    } finally {
      setUploading(false);
    }
  }

  return <form onSubmit={submit} className="mb-5 flex flex-col gap-3 rounded-2xl border border-[#e4e9e2] bg-white p-5 sm:flex-row sm:items-center">
    <div className="min-w-0 flex-1">
      <input name="resume" type="file" required disabled={uploading} accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" className="w-full text-sm" />
      {uploading && <div className="mt-3" aria-live="polite">
        <div className="h-1.5 overflow-hidden rounded-full bg-[#edf0eb]"><div className="h-full rounded-full bg-[#55705d] transition-[width]" style={{ width: `${progress}%` }} /></div>
        <p className="mt-1 text-[11px] text-[#65716c]">{progress < 100 ? `正在上传 ${progress}%` : "上传完成，正在解析并生成 Embedding…"}</p>
      </div>}
    </div>
    <button disabled={uploading} className="rounded-xl bg-[#234e43] px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50">{uploading ? "处理中…" : "上传简历"}</button>
    {message && <p role={tone === "error" ? "alert" : "status"} className={`text-xs ${tone === "error" ? "text-[#9b4e37]" : tone === "duplicate" ? "text-[#8a6718]" : "text-[#315d4f]"}`}>{message}</p>}
  </form>;
}
