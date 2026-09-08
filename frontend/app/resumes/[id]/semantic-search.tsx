"use client";

import { type FormEvent, useState } from "react";
import { api, ApiError, type RetrievalMatch } from "@/lib/api";

export function SemanticSearch({ currentDocumentId }: { currentDocumentId: string }) {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<RetrievalMatch[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    if (!normalized || loading) return;
    setLoading(true);
    setError("");
    try {
      setMatches(await api.searchDocuments(normalized, 5));
      setHasSearched(true);
    } catch (searchError) {
      setError(searchError instanceof ApiError ? searchError.message : "语义检索暂时不可用");
    } finally {
      setLoading(false);
    }
  }

  return <section className="mt-5 rounded-2xl bg-[#d9ef84] p-5 md:p-6">
    <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
      <div><p className="text-[9px] font-black uppercase tracking-[.14em] text-[#55705d]">Vector search</p><h2 className="mt-1 text-[17px] font-bold text-[#234e43]">语义检索</h2><p className="mt-1 text-xs text-[#55705d]">搜索当前用户的全部简历文本块，结果按余弦相似度排序。</p></div>
    </div>
    <form onSubmit={submit} className="mt-4 flex flex-col gap-2 sm:flex-row">
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="例如：FastAPI 后端开发经验"
        maxLength={2000}
        className="min-w-0 flex-1 rounded-xl border border-white/70 bg-white px-4 py-3 text-sm outline-none transition focus:border-[#476c5e]"
      />
      <button disabled={!query.trim() || loading} className="rounded-xl bg-[#234e43] px-5 py-3 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">{loading ? "检索中…" : "搜索"}</button>
    </form>
    {error && <p className="mt-3 rounded-xl bg-[#fbe8e5] p-3 text-xs text-[#a14d42]">{error}</p>}
    {matches.length > 0 && <div className="mt-4 space-y-2">{matches.map((match) => <article key={match.chunk_id} className="rounded-xl bg-white/85 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs font-bold text-[#315d4f]">{match.section}{match.document_id === currentDocumentId && <span className="ml-2 rounded-full bg-[#e7f0e9] px-2 py-1 text-[9px]">当前文档</span>}</span><span className="text-[10px] font-black text-[#55705d]">相似度 {(match.score * 100).toFixed(1)}%</span></div>
      <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-xs leading-6 text-[#626d68]">{match.content}</p>
    </article>)}</div>}
    {hasSearched && !loading && matches.length === 0 && !error && <p className="mt-4 rounded-xl bg-white/60 p-4 text-center text-xs text-[#65716c]">没有找到可用的匹配文本块。</p>}
  </section>;
}
