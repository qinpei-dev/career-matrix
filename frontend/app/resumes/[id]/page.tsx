import Link from "next/link";
import { notFound } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Icon } from "@/components/icons";
import { ApiError } from "@/lib/api";
import { documentsApi, type DocumentChunk } from "@/lib/documents-api";
import { SemanticSearch } from "./semantic-search";
import { DeleteDocument } from "./delete-document";
import { RetryDocument } from "./retry-document";

export const dynamic = "force-dynamic";

export default async function ResumeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const document = await documentsApi.get(id).catch((error) => {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  });
  const chunks = await documentsApi.chunks(id);
  const sections = chunks.reduce<Map<string, DocumentChunk[]>>((grouped, chunk) => {
    const entries = grouped.get(chunk.section) ?? [];
    entries.push(chunk);
    grouped.set(chunk.section, entries);
    return grouped;
  }, new Map());

  return <AppShell><div className="animate-rise">
    <Link href="/resumes" className="mb-5 inline-flex items-center gap-2 text-xs font-semibold text-[#64748b]">
      <span className="rotate-180"><Icon name="arrow" className="h-3.5 w-3.5" /></span>返回简历列表
    </Link>

    <section className="rounded-xl border border-[#e2e8f0] bg-white p-5 md:p-5">
      <div className="flex flex-col justify-between gap-5 md:flex-row md:items-start">
        <div className="flex gap-4">
          <span className="grid h-14 w-14 shrink-0 place-items-center rounded-xl bg-[#e2e8f0] text-[#2563eb]"><Icon name="file" /></span>
          <div><h1 className="break-all text-2xl font-semibold tracking-[-.02em]">{document.filename}</h1><p className="mt-2 text-sm text-[#64748b]">{document.file_type.toUpperCase()} · 上传于 {new Date(document.created_at).toLocaleString("zh-CN")}</p></div>
        </div>
        <div><div className="flex flex-wrap gap-2 text-xs"><span className="rounded-full bg-[#e2e8f0] px-3 py-2 font-semibold text-[#059669]">{document.status === "ready" ? "解析完成" : document.status === "failed" ? "解析失败" : "解析中"}</span><span className="rounded-full bg-[#f1f5f9] px-3 py-2 font-semibold text-[#64748b]">{document.chunk_count} 个文本块</span><span className={`rounded-full px-3 py-2 font-semibold ${document.rag_available ? "bg-[#e2e8f0] text-[#059669]" : "bg-[#fef3c7] text-[#92400e]"}`}>{document.rag_available ? "Embedding 就绪 · RAG 可用" : "RAG 不可用"}</span></div><div className="mt-3 flex flex-wrap justify-end gap-2">{document.can_retry && <RetryDocument documentId={document.id} />}<DeleteDocument documentId={document.id} /></div></div>
      </div>
    </section>

    {document.rag_available ? <SemanticSearch currentDocumentId={document.id} /> : <section className="mt-5 rounded-xl border border-[#fde68a] bg-[#fffbeb] p-5 text-sm text-[#92400e]">{document.status === "failed" ? "解析或 Embedding 失败。RAG 检索不会使用此文档，请重试处理。" : "文档仍在处理中，Embedding 完成后才会开放 RAG 检索。"}</section>}

    <div className="mt-5 space-y-5">
      {[...sections.entries()].map(([section, sectionChunks]) => <section key={section} className="rounded-xl border border-[#e2e8f0] bg-white p-5 md:p-6">
        <div className="flex items-center justify-between"><h2 className="text-[15px] font-semibold">{section}</h2><span className="text-[11px] font-semibold text-[#94a3b8]">{sectionChunks.length} 个文本块</span></div>
        <div className="mt-4 space-y-3">{sectionChunks.map((chunk) => <article key={chunk.chunk_id} className="rounded-xl bg-[#f1f5f9] p-4">
          <p className="mb-2 text-[11px] font-semibold text-[#94a3b8]">Chunk {chunk.chunk_index}</p>
          <p className="whitespace-pre-wrap text-sm leading-7 text-[#475569]">{chunk.content}</p>
        </article>)}</div>
      </section>)}
      {chunks.length === 0 && <section className="rounded-xl border border-[#e2e8f0] bg-white p-10 text-center text-sm text-[#64748b]">该文档暂无可展示的文本块。</section>}
    </div>
  </div></AppShell>;
}
