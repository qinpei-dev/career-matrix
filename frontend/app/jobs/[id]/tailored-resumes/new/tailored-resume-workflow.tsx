"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { SavedJob } from "@/lib/jobs-api";
import { documentsApi, type DocumentChunk, type ResumeDocument } from "@/lib/documents-api";
import {
  canGenerate,
  comparisonLabel,
  tailoredResumesApi,
  type TailoredItem,
  type TailoredResume,
  type TailoredResumeListItem,
} from "@/lib/tailored-resumes-api";

type BusyAction = "loading" | "generating" | "saving" | "finalizing" | "deleting" | "downloading" | null;

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "操作失败，请稍后重试";
}

function EditableGroup({
  title,
  items,
  disabled,
  onChange,
}: {
  title: string;
  items: TailoredItem[];
  disabled: boolean;
  onChange: (items: TailoredItem[]) => void;
}) {
  return <section>
    <h3 className="text-sm font-bold">{title}</h3>
    <div className="mt-3 space-y-3">
      {items.map((item, index) => <div key={`${item.evidence_ids.join("-")}-${index}`} className="rounded-xl border border-[#e4e9e2] p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="rounded-full bg-[#eef3ed] px-2 py-1 text-[10px] font-bold text-[#52685f]">{item.action}</span>
          <span className="text-[10px] text-[#8b9490]">{item.evidence_ids.length} 条依据</span>
        </div>
        <textarea
          value={item.text}
          disabled={disabled}
          onChange={(event) => {
            const next = [...items];
            next[index] = { ...item, text: event.target.value, action: "改写" };
            onChange(next);
          }}
          className="min-h-24 w-full resize-y rounded-lg bg-[#f7f9f6] p-3 text-sm leading-6 outline-none focus:ring-2 focus:ring-[#8eaa9f]"
        />
      </div>)}
      {items.length === 0 && <p className="rounded-xl bg-[#f7f9f6] p-4 text-xs text-[#858e8a]">原始简历没有可归入此部分的证据。</p>}
    </div>
  </section>;
}

export function TailoredResumeWorkflow({
  job,
  documents,
  initialHistory,
}: {
  job: SavedJob;
  documents: ResumeDocument[];
  initialHistory: TailoredResumeListItem[];
}) {
  const [selectedDocumentId, setSelectedDocumentId] = useState(
    initialHistory[0]?.source_document_id ?? documents[0]?.id ?? "",
  );
  const [sourceChunks, setSourceChunks] = useState<DocumentChunk[]>([]);
  const [resume, setResume] = useState<TailoredResume | null>(null);
  const [history, setHistory] = useState(initialHistory);
  const [busy, setBusy] = useState<BusyAction>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [summary, setSummary] = useState("");
  const [skillsText, setSkillsText] = useState("");
  const [experience, setExperience] = useState<TailoredItem[]>([]);
  const [projects, setProjects] = useState<TailoredItem[]>([]);
  const [education, setEducation] = useState<TailoredItem[]>([]);

  function hydrate(next: TailoredResume) {
    setResume(next);
    setSelectedDocumentId(next.source_document_id);
    setSummary(next.summary);
    setSkillsText(next.skills_json.join(", "));
    setExperience(next.experience_json);
    setProjects(next.projects_json);
    setEducation(next.education_json);
  }

  useEffect(() => {
    if (!selectedDocumentId) {
      setSourceChunks([]);
      return;
    }
    let active = true;
    documentsApi.chunks(selectedDocumentId)
      .then((chunks) => { if (active) setSourceChunks(chunks); })
      .catch((caught) => { if (active) setError(errorText(caught)); });
    return () => { active = false; };
  }, [selectedDocumentId]);

  useEffect(() => {
    const latest = initialHistory[0];
    if (!latest) return;
    let active = true;
    setBusy("loading");
    tailoredResumesApi.get(latest.id)
      .then((value) => { if (active) hydrate(value); })
      .catch((caught) => { if (active) setError(errorText(caught)); })
      .finally(() => { if (active) setBusy(null); });
    return () => { active = false; };
  }, [initialHistory]);

  const sourceSummary = useMemo(
    () => sourceChunks
      .filter((chunk) => /summary|profile|简介|概述|优势/i.test(chunk.section))
      .map((chunk) => chunk.content)
      .join("\n") || sourceChunks[0]?.content || "",
    [sourceChunks],
  );
  const original = resume?.generated_content_json.original;
  const finalized = resume?.status === "FINALIZED";
  const generated = Boolean(
    resume && ["GENERATED", "EDITING", "FINALIZED"].includes(resume.status),
  );
  const generationEnabled = resume
    ? canGenerate(resume.status, busy !== null)
    : busy === null;

  async function generate() {
    if (!selectedDocumentId || busy) return;
    setBusy("generating");
    setError("");
    setSuccess("");
    try {
      let id = resume?.source_document_id === selectedDocumentId ? resume.id : "";
      if (!id || resume?.status === "FINALIZED") {
        const created = await tailoredResumesApi.create({
          job_id: job.id,
          source_document_id: selectedDocumentId,
        });
        id = created.tailored_resume_id;
      }
      const next = await tailoredResumesApi.generate(id);
      hydrate(next);
      setHistory(await tailoredResumesApi.list(job.id));
      setSuccess("定制版本已生成；所有写入内容均已通过原始简历证据校验。");
    } catch (caught) {
      setError(errorText(caught));
      if (resume) {
        tailoredResumesApi.get(resume.id).then(hydrate).catch(() => undefined);
      }
    } finally {
      setBusy(null);
    }
  }

  async function save() {
    if (!resume || busy || finalized) return;
    setBusy("saving");
    setError("");
    setSuccess("");
    try {
      const next = await tailoredResumesApi.update(resume.id, {
        summary,
        skills: skillsText.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean),
        experience,
        projects,
        education,
      });
      hydrate(next);
      setSuccess("草稿已保存，刷新页面后仍可恢复。");
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(null);
    }
  }

  async function finalize() {
    if (!resume || busy || finalized || !window.confirm("最终确认后将禁止继续编辑和直接删除，是否继续？")) return;
    setBusy("finalizing");
    setError("");
    try {
      const next = await tailoredResumesApi.finalize(resume.id);
      hydrate(next);
      setSuccess("定制简历已最终确认。");
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (!resume || busy || finalized || !window.confirm("确定删除这个未最终确认的定制版本吗？此操作不可撤销。")) return;
    setBusy("deleting");
    setError("");
    try {
      await tailoredResumesApi.delete(resume.id);
      setResume(null);
      setSummary("");
      setSkillsText("");
      setExperience([]);
      setProjects([]);
      setEducation([]);
      const nextHistory = await tailoredResumesApi.list(job.id);
      setHistory(nextHistory);
      setSuccess("草稿已删除。");
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(null);
    }
  }

  async function loadVersion(id: string) {
    if (busy) return;
    setBusy("loading");
    setError("");
    try {
      hydrate(await tailoredResumesApi.get(id));
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(null);
    }
  }

  async function downloadDocx() {
    if (!resume || busy) return;
    setBusy("downloading");
    setError("");
    try {
      const blob = await tailoredResumesApi.downloadDocx(resume.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "tailored-resume.docx";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(null);
    }
  }

  return <div className="mt-7 space-y-5">
    <section className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5 md:p-6">
      <div className="grid gap-5 lg:grid-cols-2">
        <div>
          <label htmlFor="source-resume" className="text-sm font-bold">1. 选择原始简历</label>
          {documents.length > 0 ? <select
            id="source-resume"
            value={selectedDocumentId}
            disabled={busy !== null}
            onChange={(event) => {
              setSelectedDocumentId(event.target.value);
              setResume(null);
              setError("");
            }}
            className="mt-3 w-full rounded-xl border border-[#dfe5de] bg-white px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[#8eaa9f]"
          >
            {documents.map((document) => <option key={document.id} value={document.id}>
              {document.filename} · {document.chunk_count} 个证据块
            </option>)}
          </select> : <div className="mt-3 rounded-xl border border-[#eadbb0] bg-[#fff9e8] p-4 text-sm text-[#765f26]">
            没有解析和 Embedding 就绪的简历。<Link href="/resumes" className="ml-1 font-bold underline">先上传简历</Link>
          </div>}
          {sourceSummary && <div className="mt-4 rounded-xl bg-[#f6f8f4] p-4">
            <p className="text-[10px] font-black uppercase tracking-[.12em] text-[#8b9490]">原始简历摘要</p>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#606b66]">{sourceSummary}</p>
          </div>}
        </div>
        <div className="rounded-xl bg-[#f6f8f4] p-4">
          <p className="text-[10px] font-black uppercase tracking-[.12em] text-[#8b9490]">目标岗位</p>
          <h2 className="mt-2 font-bold">{job.title}</h2>
          <p className="mt-1 text-xs text-[#7b8581]">{job.company || "未填写公司"}</p>
          <p className="mt-3 line-clamp-6 whitespace-pre-wrap text-sm leading-6 text-[#606b66]">{job.description}</p>
        </div>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          onClick={generate}
          disabled={!selectedDocumentId || !generationEnabled}
          className="rounded-xl bg-[#315d4f] px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy === "generating"
            ? "正在检索证据并生成…"
            : finalized
              ? "基于此版本创建新定制简历"
              : resume?.status === "FAILED"
                ? "重试生成"
                : "生成定制简历"}
        </button>
        {resume && <span className="rounded-full bg-[#eef3ed] px-3 py-2 text-xs font-bold text-[#52685f]">
          {finalized ? "已完成版本" : resume.status} · v{resume.version}
        </span>}
        <span className="text-xs text-[#7f8985]">按钮忙碌期间不可重复提交</span>
      </div>
    </section>

    {error && <div role="alert" className="rounded-2xl border border-[#ebc7c1] bg-[#fff4f2] p-4 text-sm text-[#973f35]">{error}</div>}
    {success && <div role="status" className="rounded-2xl border border-[#cfe0d2] bg-[#f0f8f1] p-4 text-sm text-[#356348]">{success}</div>}
    {resume?.status === "FAILED" && <div className="rounded-2xl border border-[#ebc7c1] bg-[#fff4f2] p-4 text-sm text-[#973f35]">
      生成失败：{resume.error_message || "未知错误"}。可使用上方“重试生成”继续。
    </div>}

    {generated && resume && <>
      <section className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5 md:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="text-lg font-bold">2. 原版 / 定制版对比</h2><p className="mt-1 text-xs text-[#7c8682]">每项状态与 evidence 均来自真实 API。</p></div>
          <span className="rounded-full bg-[#e7f0e9] px-3 py-2 text-xs font-bold text-[#3d6c50]">
            证据 {resume.evidence_json.length} 条
          </span>
        </div>
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl bg-[#f6f8f4] p-4">
            <h3 className="text-sm font-bold">原职业摘要</h3>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#66716c]">{original?.summary || "原简历未识别到摘要"}</p>
          </div>
          <div className="rounded-xl border border-[#dce7de] bg-[#f7fbf7] p-4">
            <div className="flex justify-between"><h3 className="text-sm font-bold">定制摘要</h3><span className="text-[10px] font-bold text-[#527060]">{comparisonLabel(original?.summary || "", summary)}</span></div>
            <textarea value={summary} disabled={finalized} onChange={(event) => setSummary(event.target.value)} className="mt-3 min-h-32 w-full resize-y rounded-lg bg-white p-3 text-sm leading-6 outline-none focus:ring-2 focus:ring-[#8eaa9f]" />
          </div>
          <div className="rounded-xl bg-[#f6f8f4] p-4">
            <h3 className="text-sm font-bold">原技能顺序</h3>
            <p className="mt-3 text-sm leading-6 text-[#66716c]">{original?.skills?.join(" · ") || "未识别"}</p>
          </div>
          <div className="rounded-xl border border-[#dce7de] bg-[#f7fbf7] p-4">
            <h3 className="text-sm font-bold">定制技能顺序</h3>
            <textarea value={skillsText} disabled={finalized} onChange={(event) => setSkillsText(event.target.value)} className="mt-3 min-h-24 w-full resize-y rounded-lg bg-white p-3 text-sm leading-6 outline-none focus:ring-2 focus:ring-[#8eaa9f]" />
          </div>
        </div>
        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <EditableGroup title="经历重点" items={experience} disabled={finalized} onChange={setExperience} />
          <EditableGroup title="项目描述" items={projects} disabled={finalized} onChange={setProjects} />
          <EditableGroup title="教育经历" items={education} disabled={finalized} onChange={setEducation} />
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-2xl border border-[#d7e5d9] bg-[#f2f8f2] p-5">
          <h2 className="font-bold text-[#365e45]">JD 关键词覆盖</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {(resume.generated_content_json.keyword_coverage?.covered || []).map((keyword) => <span key={keyword} className="rounded-full bg-white px-3 py-1.5 text-xs font-bold text-[#3d6c50]">保留 · {keyword}</span>)}
            {(resume.generated_content_json.keyword_coverage?.covered || []).length === 0 && <span className="text-sm text-[#63806d]">没有可由原简历证据支持的 JD 关键词。</span>}
          </div>
        </div>
        <div className="rounded-2xl border border-[#eadbb0] bg-[#fff9e8] p-5">
          <h2 className="font-bold text-[#765f26]">缺失与风险提示</h2>
          <div className="mt-3 space-y-2">
            {resume.warnings_json.map((warning, index) => <div key={`${warning.code}-${warning.keyword}-${index}`} className="rounded-xl bg-white/70 p-3 text-sm text-[#735d2b]">
              <span className="mr-2 rounded-full bg-[#f9e8b7] px-2 py-1 text-[10px] font-bold">{warning.action}</span>{warning.message}
            </div>)}
            {resume.warnings_json.length === 0 && <p className="text-sm">未发现无证据建议。</p>}
          </div>
        </div>
      </section>

      <section className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5 md:p-6">
        <h2 className="font-bold">修改依据</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {resume.evidence_json.map((item) => <article key={item.id} className="rounded-xl bg-[#f6f8f4] p-4">
            <div className="flex justify-between text-[10px] font-bold text-[#84908b]"><span>{item.section}</span><span>{item.rag_score === null ? "源 chunk" : `RAG ${item.rag_score.toFixed(3)}`}</span></div>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#606b66]">{item.content}</p>
          </article>)}
        </div>
      </section>

      <section className="sticky bottom-4 z-10 flex flex-wrap gap-3 rounded-2xl border border-[#dce3dc] bg-white/95 p-4 shadow-lg backdrop-blur">
        <button onClick={save} disabled={busy !== null || finalized} className="rounded-xl bg-[#315d4f] px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">{busy === "saving" ? "保存中…" : "保存草稿"}</button>
        <button onClick={finalize} disabled={busy !== null || finalized} className="rounded-xl border border-[#315d4f] px-4 py-2.5 text-sm font-bold text-[#315d4f] disabled:opacity-50">{busy === "finalizing" ? "确认中…" : finalized ? "已最终确认" : "最终确认"}</button>
        <button onClick={downloadDocx} disabled={busy !== null} className="rounded-xl border border-[#d9dfd9] px-4 py-2.5 text-sm font-bold text-[#4d5d56] disabled:opacity-50">{busy === "downloading" ? "下载中…" : "下载 DOCX"}</button>
        <button disabled title="PDF export NOT VERIFIED" className="rounded-xl border border-dashed border-[#d9dfd9] px-4 py-2.5 text-sm font-bold text-[#929a96]">PDF · NOT VERIFIED</button>
        <button onClick={remove} disabled={busy !== null || finalized} className="ml-auto rounded-xl px-4 py-2.5 text-sm font-bold text-[#a14d42] disabled:opacity-40">{busy === "deleting" ? "删除中…" : "删除草稿"}</button>
      </section>
    </>}

    {history.length > 0 && <section className="rounded-2xl border border-[#e4e9e2] bg-white p-5">
      <h2 className="font-bold">历史版本</h2>
      <div className="mt-3 flex flex-wrap gap-2">{history.map((item) => <button key={item.id} onClick={() => loadVersion(item.id)} disabled={busy !== null} className="rounded-xl border border-[#e0e5df] px-3 py-2 text-left text-xs hover:bg-[#f6f8f4]">
        <strong>{item.status}</strong> · {new Date(item.updated_at).toLocaleString("zh-CN")}
      </button>)}</div>
    </section>}
  </div>;
}
