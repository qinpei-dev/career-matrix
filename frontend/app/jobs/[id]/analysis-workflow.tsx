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
    <section className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-6">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[.14em] text-[#6b887c]">AI match report</p>
          <div className="mt-2 flex items-center gap-2">
            <h2 className="text-lg font-bold">岗位匹配分析</h2>
            <StatusPill status={statusLabels[visibleStatus]}/>
          </div>
          {task && <p className="mt-2 text-xs text-[#78827e]">
            当前步骤：{statusLabels[task.current_step as AnalysisTaskStatus] ?? task.current_step}
            {" · "}重试 {task.retry_count}/{task.max_retries}
          </p>}
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right"><span className="text-4xl font-semibold tracking-[-.06em]">{analysis?.score ?? "—"}</span><span className="text-sm text-[#8b9490]"> / 100</span></div>
          <button type="button" onClick={action.handler} disabled={actionDisabled}
            className="rounded-xl bg-[#234e43] px-4 py-2.5 text-xs font-bold text-white transition hover:bg-[#193c34] disabled:cursor-wait disabled:bg-[#8a9b95]">
            {busy ? "处理中…" : action.label}
          </button>
        </div>
      </div>
      {task && <div className="mt-5">
        <div className="mb-2 flex justify-between text-[11px] text-[#7d8783]">
          <span>{statusLabels[task.status]}</span><span>{task.progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-[#edf0eb]">
          <div className="h-full rounded-full bg-[#7ca383] transition-[width]" style={{width: `${task.progress}%`}}/>
        </div>
      </div>}
      {(error || task?.error_message) && <p role="alert" className="mt-4 rounded-xl bg-[#fff1ea] px-4 py-3 text-sm text-[#9b4e37]">{error || task?.error_message}</p>}
      {recoveryFailed && <button type="button" onClick={() => void loadPersistedTask()} disabled={busy}
        className="mt-3 rounded-lg border border-[#cbd5cf] px-3 py-2 text-xs font-bold text-[#315d4f] disabled:opacity-50">
        重新加载状态
      </button>}
      {task?.status === "WAITING_FOR_REVIEW" && <p className="mt-4 text-sm leading-7 text-[#65706b]">分析结果已安全保存，请审核后确认完成。</p>}
      {task?.status === "COMPLETED" && <p className="mt-4 text-sm leading-7 text-[#65706b]">分析已由你确认完成。</p>}
    </section>

    {analysis && <section className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-6">
      <div className="grid gap-6 sm:grid-cols-2">
        <div><h3 className="text-[15px] font-bold">匹配理由</h3>{reasons.length ? <ul className="mt-4 space-y-3">{reasons.map((reason) => <li key={reason} className="text-sm leading-6 text-[#65706b]">• {reason}</li>)}</ul> : <p className="mt-4 text-sm text-[#8a938f]">暂无额外匹配理由。</p>}</div>
        <div><h3 className="text-[15px] font-bold">能力缺口</h3>{gaps.length ? <div className="mt-4 flex flex-wrap gap-2">{gaps.map((gap) => <span key={gap} className="rounded-lg bg-[#f7eadf] px-2.5 py-1.5 text-[11px] font-semibold text-[#8b5e3b]">{gap}</span>)}</div> : <p className="mt-4 text-sm text-[#8a938f]">未识别到明确缺口。</p>}</div>
      </div>
      <div className="mt-6 border-t border-[#edf0eb] pt-5">
        <h3 className="text-[15px] font-bold">引用证据 <span className="text-[10px] text-[#929a96]">{evidence.length} 条</span></h3>
        {evidence.length ? <div className="mt-4 grid gap-3">{evidence.map((item) => <article key={`${item.requirement}-${item.chunk_id}`} className="rounded-xl bg-[#f6f8f4] p-4"><h4 className="text-xs font-bold text-[#315d4f]">{item.requirement}</h4><p className="mt-2 text-xs leading-6 text-[#626d68]">{item.content}</p></article>)}</div> : <p className="mt-4 text-sm text-[#8a938f]">暂无可引用的简历向量证据。</p>}
      </div>
    </section>}
  </div>;
}
