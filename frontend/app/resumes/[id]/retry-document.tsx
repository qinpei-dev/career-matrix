"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { documentsApi } from "@/lib/documents-api";

export function RetryDocument({ documentId }: { documentId: string }) {
  const router = useRouter();
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState("");

  async function retry() {
    if (retrying) return;
    setRetrying(true);
    setError("");
    try {
      await documentsApi.retry(documentId);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "重试失败");
    } finally {
      setRetrying(false);
    }
  }

  return <div>
    <button type="button" onClick={retry} disabled={retrying} className="rounded-xl bg-[#234e43] px-3 py-2 text-xs font-bold text-white disabled:opacity-50">
      {retrying ? "重新解析并生成 Embedding…" : "重试解析"}
    </button>
    {error && <p role="alert" className="mt-2 max-w-sm text-xs text-[#9b4e37]">{error}</p>}
  </div>;
}
