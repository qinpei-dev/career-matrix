"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { StatusPill } from "@/components/ui";
import {
  api,
  ApiError,
  type Analysis,
  type AnalysisTask,
  type AnalysisTaskStatus,
} from "@/lib/api";
import {
  shouldDeleteCachedTask,
  hasTaskPollingTimedOut,
  shouldPollAnalysisTask,
  TASK_POLL_INTERVAL_MS,
} from "@/lib/analysis-task-recovery";

const statusLabels: Record<AnalysisTaskStatus, string> = {
  PENDING: "等待执行",
  FETCHING_JOB: "读取岗位信息",
  ANALYZING: "AI 正在分析",
  SAVING_RESULT: "保存分析结果",
  WAITING_FOR_REVIEW: "等待用户确认",
  COMPLETED: "分析完成",
  FAILED: "执行失败",
};

function stringList(result: Record<string, unknown>, key: string): string[] {
  const value = result[key];
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function scoreReasons(result: Record<string, unknown>): string[] {
  const breakdown = result.score_breakdown;
  if (typeof breakdown !== "object" || breakdown === null) return [];
  return Object.values(breakdown).flatMap((dimension) => {
    if (typeof dimension !== "object" || dimension === null) return [];
    const record = dimension as Record<string, unknown>;
    return typeof record.reason === "string" && record.applicable !== false
      ? [record.reason]
      : [];
  });
}

export function AnalysisWorkflow({
  jobId,
  initialAnalysis,
}: {
  jobId: string;
  initialAnalysis?: Analysis;
}) {
  const router = useRouter();
  const storageKey = `analysis-task:${jobId}`;
  const [task, setTask] = useState<AnalysisTask | null>(null);
  const [analysis, setAnalysis] = useState(initialAnalysis);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recoveryFailed, setRecoveryFailed] = useState(false);
  const pollStartedAt = useRef(0);
  const pollTaskId = useRef<string | null>(null);
  const pollInFlight = useRef(false);
  const result = analysis?.result_json ?? {};
  const modelReasons = stringList(result, "reasoning");
  const reasons = modelReasons.length ? modelReasons : scoreReasons(result);
  const gaps = stringList(result, "missing_skills");
  const strengths = stringList(result, "matched_skills");
  const partial = stringList(result, "partial_skills");
  const learningPlan = stringList(result, "learning_plan");
  const projectEvidence = stringList(result, "project_evidence");
  const experienceEvidence = stringList(result, "experience_evidence");
  const greeting = typeof result.greeting === "string" ? result.greeting : "";
  const summary = typeof result.summary === "string" ? result.summary : "";
  const evidence = analysis?.evidence_json ?? [];

  const syncAnalysis = useCallback(async (current: AnalysisTask) => {
    if (!current.result_id) return;
    const analyses = await api.getAnalyses();
    setAnalysis(analyses.find((item) => item.id === current.result_id));
  }, []);

  const loadPersistedTask = useCallback(async () => {
    const taskId = window.localStorage.getItem(storageKey);
    pollTaskId.current = null;
    pollStartedAt.current = 0;
    setRecoveryFailed(false);
    setError(null);
    try {
      const current = await api.getActiveAnalysisTask(jobId);
      if (!current) return;
      window.localStorage.setItem(storageKey, current.id);
      setTask(current);
      await syncAnalysis(current);
      return;
    } catch (caught) {
      if (!(caught instanceof ApiError && caught.status === 404)) {
        setRecoveryFailed(true);
        setError(caught instanceof Error ? caught.message : "无法读取任务状态");
        return;
      }
    }
    if (!taskId) return;
    try {
      const current = await api.getAnalysisTask(taskId);
      setTask(current);
      await syncAnalysis(current);
    } catch (caught) {
      if (shouldDeleteCachedTask(caught)) {
        window.localStorage.removeItem(storageKey);
        setTask(null);
        setError("任务不存在，可重新创建");
      } else {
        setRecoveryFailed(true);
        setError(caught instanceof Error ? caught.message : "无法读取任务状态");
      }
    }
  }, [jobId, storageKey, syncAnalysis]);

  useEffect(() => {
    void loadPersistedTask();
  }, [loadPersistedTask]);

  useEffect(() => {
    if (!task || !shouldPollAnalysisTask(task)) {
      pollTaskId.current = null;
      pollStartedAt.current = 0;
      return;
    }
    if (pollTaskId.current !== task.id) {
      pollTaskId.current = task.id;
      pollStartedAt.current = Date.now();
    }
    let stopped = false;
    const timer = window.setInterval(async () => {
      if (stopped || pollInFlight.current) return;
      if (hasTaskPollingTimedOut(pollStartedAt.current, Date.now())) {
        window.clearInterval(timer);
        setRecoveryFailed(true);
        setError("状态查询已暂停，请刷新或重新加载状态");
        return;
      }
      pollInFlight.current = true;
      try {
        const current = await api.getAnalysisTask(task.id);
        if (!stopped) {
          setTask(current);
          await syncAnalysis(current);
        }
      } catch (caught) {
        if (!stopped) {
          if (shouldDeleteCachedTask(caught)) {
            window.localStorage.removeItem(storageKey);
            setTask(null);
            setError("任务不存在，可重新创建");
          } else {
            setRecoveryFailed(true);
            setError(caught instanceof Error ? caught.message : "无法读取任务状态");
          }
        }
      } finally {
        pollInFlight.current = false;
      }
    }, TASK_POLL_INTERVAL_MS);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [storageKey, syncAnalysis, task]);

  async function startAnalysis() {
    setBusy(true);
    setError(null);
    try {
      const settings = await api.getSettings();
      const started = await api.createAnalysisTask(jobId);
      window.localStorage.setItem(storageKey, started.task_id);
      const pending = await api.getAnalysisTask(started.task_id);
      setTask(pending);
      if (!settings.default_analysis_options.auto_run) {
        router.refresh();
        return;
      }
      const current = await api.runAnalysisTask(started.task_id);
      setTask(current);
      await syncAnalysis(current);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "分析任务执行失败");
    } finally {
      setBusy(false);
    }
  }

  async function retry() {
    if (!task) return;
    setBusy(true);
    setError(null);
    try {
      const current = await api.retryAnalysisTask(task.id);
      setTask(current);
      await syncAnalysis(current);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "重新执行失败");
    } finally {
      setBusy(false);
    }
  }

  async function continueTask() {
    if (!task) return;
    setBusy(true);
    setError(null);
    try {
      const current = await api.runAnalysisTask(task.id);
      setTask(current);
      await syncAnalysis(current);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "继续执行失败");
    } finally {
      setBusy(false);
    }
  }

  async function complete() {
    if (!task) return;
    setBusy(true);
    setError(null);
    try {
      const current = await api.completeAnalysisTask(task.id);
      setTask(current);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "确认失败");
    } finally {
      setBusy(false);
    }
  }

  const visibleStatus = task?.status ?? (analysis ? "COMPLETED" : "PENDING");
  const action = task?.status === "FAILED"
    ? { label: "重新执行", handler: retry }
    : task?.status === "WAITING_FOR_REVIEW"
      ? { label: "确认完成", handler: complete }
      : task?.status === "COMPLETED"
        ? { label: "分析完成", handler: continueTask }
        : task
          ? { label: "继续执行", handler: continueTask }
          : { label: "开始 AI 分析", handler: startAnalysis };
  const actionDisabled = busy || task?.is_running || task?.status === "COMPLETED";

  return <div className="space-y-5">
    <section className="rounded-xl border border-[#e4e4e7] bg-white p-6">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
        <div>
          <p className="text-[11px] font-semibold text-[#27272a]">AI match report</p>
          <div className="mt-2 flex items-center gap-2">
            <h2 className="text-lg font-semibold">岗位匹配分析</h2>
            <StatusPill status={statusLabels[visibleStatus]}/>
          </div>
          {task && <p className="mt-2 text-xs text-[#71717a]">
            当前步骤：{statusLabels[task.current_step as AnalysisTaskStatus] ?? task.current_step}
            {" · "}重试 {task.retry_count}/{task.max_retries}
          </p>}
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right"><span className="text-4xl font-semibold tracking-[-.02em]">{analysis?.score ?? "—"}</span><span className="text-sm text-[#a1a1aa]"> / 100</span></div>
          <button type="button" onClick={action.handler} disabled={actionDisabled}
            className="rounded-xl bg-[#18181b] px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-[#18181b] disabled:cursor-wait disabled:bg-[#a1a1aa]">
            {busy ? "处理中…" : action.label}
          </button>
        </div>
      </div>
      {task && <div className="mt-5">
        <div className="mb-2 flex justify-between text-[11px] text-[#71717a]">
          <span>{statusLabels[task.status]}</span><span>{task.progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-[#e4e4e7]">
          <div className="h-full rounded-full bg-[#34d399] transition-[width]" style={{width: `${task.progress}%`}}/>
        </div>
      </div>}
      {(error || task?.error_message) && <p role="alert" className="mt-4 rounded-xl bg-[#fef2f2] px-4 py-3 text-sm text-[#b91c1c]">{error || task?.error_message}</p>}
      {recoveryFailed && <button type="button" onClick={() => void loadPersistedTask()} disabled={busy}
        className="mt-3 rounded-lg border border-[#d4d4d8] px-3 py-2 text-xs font-semibold text-[#18181b] disabled:opacity-50">
        重新加载状态
      </button>}
      {task?.status === "WAITING_FOR_REVIEW" && <p className="mt-4 text-sm leading-7 text-[#71717a]">分析结果已安全保存，请审核后确认完成。</p>}
      {task?.status === "COMPLETED" && <p className="mt-4 text-sm leading-7 text-[#71717a]">分析已由你确认完成。</p>}
    </section>

    {analysis && <section className="rounded-xl border border-[#e4e4e7] bg-white p-6">
      {summary && <p className="mb-6 rounded-xl bg-[#f4f4f5] p-4 text-sm leading-7 text-[#52525b]">{summary}</p>}
      <div className="grid gap-6 sm:grid-cols-2">
        <div><h3 className="text-[15px] font-semibold">匹配理由</h3>{reasons.length ? <ul className="mt-4 space-y-3">{reasons.map((reason) => <li key={reason} className="text-sm leading-6 text-[#71717a]">• {reason}</li>)}</ul> : <p className="mt-4 text-sm text-[#71717a]">暂无额外匹配理由。</p>}</div>
        <div><h3 className="text-[15px] font-semibold">能力缺口</h3>{gaps.length ? <div className="mt-4 flex flex-wrap gap-2">{gaps.map((gap) => <span key={gap} className="rounded-lg bg-[#fef3c7] px-2.5 py-1.5 text-[11px] font-semibold text-[#b45309]">{gap}</span>)}</div> : <p className="mt-4 text-sm text-[#71717a]">未识别到明确缺口。</p>}</div>
      </div>
      <div className="mt-6 grid gap-5 border-t border-[#e4e4e7] pt-5 md:grid-cols-3">
        <div><h3 className="text-sm font-semibold">优势</h3><p className="mt-2 text-xs leading-6 text-[#71717a]">{strengths.length ? strengths.join("、") : "暂无已验证优势"}</p></div>
        <div><h3 className="text-sm font-semibold">部分匹配</h3><p className="mt-2 text-xs leading-6 text-[#71717a]">{partial.length ? partial.join("、") : "暂无部分匹配项"}</p></div>
        <div><h3 className="text-sm font-semibold">改进建议</h3><p className="mt-2 text-xs leading-6 text-[#71717a]">{learningPlan.length ? learningPlan.join("；") : "暂无额外建议"}</p></div>
      </div>
      {(projectEvidence.length > 0 || experienceEvidence.length > 0) && <div className="mt-6 border-t border-[#e4e4e7] pt-5">
        <h3 className="text-[15px] font-semibold">面试准备要点</h3>
        <ul className="mt-3 space-y-2 text-xs leading-6 text-[#71717a]">
          {[...projectEvidence, ...experienceEvidence].map((item) => <li key={item}>• {item}</li>)}
        </ul>
      </div>}
      {greeting && <div className="mt-6 border-t border-[#e4e4e7] pt-5">
        <h3 className="text-[15px] font-semibold">沟通草稿</h3>
        <p className="mt-3 whitespace-pre-line rounded-xl bg-[#f4f4f5] p-4 text-sm leading-7 text-[#52525b]">{greeting}</p>
        <p className="mt-2 text-[11px] text-[#71717a]">仅供复制和人工审核，系统不会自动发送或投递。</p>
      </div>}
      <div className="mt-6 border-t border-[#e4e4e7] pt-5">
        <h3 className="text-[15px] font-semibold">引用证据 <span className="text-[11px] text-[#a1a1aa]">{evidence.length} 条</span></h3>
        {evidence.length ? <div className="mt-4 grid gap-3">{evidence.map((item) => <article key={`${item.requirement}-${item.chunk_id}`} className="rounded-xl bg-[#f4f4f5] p-4"><h4 className="text-xs font-semibold text-[#18181b]">{item.requirement}</h4><p className="mt-2 text-xs leading-6 text-[#52525b]">{item.content}</p></article>)}</div> : <p className="mt-4 text-sm text-[#71717a]">暂无可引用的简历向量证据。</p>}
      </div>
    </section>}
  </div>;
}
