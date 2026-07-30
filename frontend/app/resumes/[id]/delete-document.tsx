"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { documentsApi } from "@/lib/documents-api";

export function DeleteDocument({ documentId }: { documentId: string }) {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");

  async function remove() {
    if (!window.confirm("确认删除这份简历及其全部文本块？此操作不可撤销。")) return;
    setDeleting(true);
    setError("");
    try {
      await documentsApi.delete(documentId);
      router.push("/resumes");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "删除失败");
      setDeleting(false);
    }
  }

  return <div className="text-right">
    <button type="button" onClick={remove} disabled={deleting} className="rounded-xl border border-[#e9cfc5] px-3 py-2 text-xs font-bold text-[#9b4e37] disabled:opacity-50">{deleting ? "删除中…" : "删除文档"}</button>
    {error && <p role="alert" className="mt-2 text-xs text-[#9b4e37]">{error}</p>}
  </div>;
}
