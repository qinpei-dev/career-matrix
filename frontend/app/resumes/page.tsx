import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Icon } from "@/components/icons";
import { PageHeading } from "@/components/ui";
import { documentsApi } from "@/lib/documents-api";
import { ResumeUpload } from "./resume-upload";

export const dynamic = "force-dynamic";

const statusStyles: Record<string, string> = {
  ready: "bg-[#e4e4e7] text-[#059669]",
  processing: "bg-[#fef3c7] text-[#92400e]",
  failed: "bg-[#fee2e2] text-[#b91c1c]",
};

const statusLabels: Record<string, string> = {
  ready: "解析完成",
  processing: "解析中",
  failed: "解析失败",
};

export default async function ResumesPage() {
  const documents = await documentsApi.list();

  return <AppShell><div className="animate-rise">
    <PageHeading
      eyebrow="Resume knowledge base"
      title="简历文档"
      description="查看已上传简历的解析状态、文本块数量和结构化内容。"
    />

    <ResumeUpload />

    <section className="overflow-hidden rounded-xl border border-[#e4e4e7] bg-white">
      {documents.length > 0 && <div className="hidden grid-cols-[minmax(240px,1.4fr)_100px_120px_120px_130px_24px] px-5 py-4 text-[11px] font-semibold text-[#a1a1aa] md:grid">
        <span>文件名</span><span>类型</span><span>状态</span><span>文本块</span><span>上传时间</span><span />
      </div>}

      {documents.map((document) => <Link
        key={document.id}
        href={`/resumes/${encodeURIComponent(document.id)}`}
        className="grid gap-3 border-t border-[#e4e4e7] px-5 py-5 transition first:border-t-0 hover:bg-[#fafafa] md:grid-cols-[minmax(240px,1.4fr)_100px_120px_120px_130px_24px] md:items-center"
      >
        <span className="flex min-w-0 items-center gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#e4e4e7] text-[#18181b]"><Icon name="file" /></span>
          <span className="truncate text-sm font-semibold">{document.filename}</span>
        </span>
        <span className="text-xs font-semibold uppercase text-[#71717a]">{document.file_type}</span>
        <span><span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${statusStyles[document.status] ?? "bg-[#e4e4e7] text-[#71717a]"}`}>{statusLabels[document.status] ?? document.status}</span></span>
        <span className="text-xs text-[#71717a]">{document.rag_available ? `${document.chunk_count} 块 · RAG 可用` : document.status === "failed" ? "RAG 不可用 · 可重试" : "RAG 准备中"}</span>
        <time className="text-xs text-[#71717a]">{new Date(document.created_at).toLocaleDateString("zh-CN")}</time>
        <Icon name="arrow" className="hidden h-4 w-4 text-[#71717a] md:block" />
      </Link>)}

      {documents.length === 0 && <div className="px-6 py-16 text-center">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-[#e4e4e7] text-[#18181b]"><Icon name="file" /></span>
        <h2 className="mt-4 text-sm font-semibold">暂无简历文档</h2>
        <p className="mt-2 text-xs text-[#71717a]">上传 PDF 或 DOCX 简历后，这里会显示真实解析与 RAG 状态。</p>
      </div>}
    </section>
    <p className="mt-4 text-center text-[11px] text-[#71717a]">来自 Document API · 共 {documents.length} 份文档</p>
  </div></AppShell>;
}
