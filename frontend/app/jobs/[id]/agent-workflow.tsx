"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, type AgentRun, type AgentStepStatus } from "@/lib/api";
import { agentRunsApi } from "@/lib/agent-runs-api";

const stepLabels: Record<string, string> = {
  validate_input: "校验岗位与用户资料",
  extract_job_requirements: "提取岗位要求",
  retrieve_candidate_evidence: "检索简历证据",
  calculate_score: "完成确定性评分",
  generate_analysis: "生成匹配分析",
  save_result: "保存分析结果",
};

const statusMarks: Record<AgentStepStatus, string> = {
  completed: "✓",
  running: "…",
  failed: "!",
};

export function AgentWorkflow({ jobId }: { jobId: string }) {
  const storageKey = `career-copilot-run:${jobId}`;
  const [run, setRun] = useState<AgentRun | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshRun = useCallback(async (id: string) => {
    const current = await agentRunsApi.get(id);
    setRun(current);
    return current;
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem(storageKey);
    if (saved) {
      setRunId(saved);
      return;
    }
    void agentRunsApi.getActive(jobId).then((current) => {
      if (!current) return;
      window.localStorage.setItem(storageKey, current.run_id);
      setRun(current);
      setRunId(current.run_id);
    }).catch((caught) => {
      if (!(caught instanceof ApiError && caught.status === 404)) {
        setError(caught instanceof Error ? caught.message : "无法恢复 Agent 状态");
      }
    });
  }, [jobId, storageKey]);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const current = await refreshRun(runId as string);
        if (!cancelled && (current.status === "pending" || current.status === "running")) {
          timer = setTimeout(poll, 750);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "无法读取 Agent 状态");
        }
      }
    }
    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [refreshRun, runId]);

  async function start() {
    setStarting(true);
    setError(null);
    setRun(null);
    try {
      const started = await agentRunsApi.create(jobId);
      window.localStorage.setItem(storageKey, started.run_id);
      setRunId(started.run_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Agent 启动失败");
    } finally {
      setStarting(false);
    }
  }

  const active = starting || run?.status === "pending" || run?.status === "running";
  return <section className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5">
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-[10px] font-black uppercase tracking-[.14em] text-[#6b887c]">Career Copilot Agent</p>
        <h2 className="mt-2 text-[15px] font-bold">Agent Timeline</h2>
      </div>
      {run && <span className={`rounded-full px-2 py-1 text-[9px] font-black ${
        run.status === "completed" ? "bg-[#e7f0eb] text-[#315d4f]"
          : run.status === "failed" || run.status === "timeout" ? "bg-[#fff1ea] text-[#9b4e37]"
            : "bg-[#f3f5d8] text-[#65712b]"
      }`}>{run.status}</span>}
    </div>

    {run?.steps.length ? <ol className="mt-5 space-y-3">
      {run.steps.map((step) => <li key={step.id} className="flex gap-3">
        <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-black ${
          step.status === "completed" ? "bg-[#d9ef84] text-[#234e43]"
            : step.status === "failed" ? "bg-[#f7d9cc] text-[#9b4e37]"
              : "animate-pulse bg-[#e7f0eb] text-[#315d4f]"
        }`}>{statusMarks[step.status]}</span>
        <div className="min-w-0 pt-0.5">
          <p className="text-xs font-bold">{stepLabels[step.step_name] ?? step.step_name}</p>
          {step.output_summary && <p className="mt-1 text-[10px] leading-4 text-[#7b8581]">{step.output_summary}</p>}
          {step.duration_ms !== null && <p className="mt-1 text-[9px] text-[#9aa19e]">{step.duration_ms} ms</p>}
        </div>
      </li>)}
    </ol> : <p className="mt-4 text-xs leading-5 text-[#6f7975]">运行后，这里会展示后端实际记录的每一步，不使用模拟数据。</p>}

    {run?.result && <div className="mt-5 rounded-xl bg-[#f4f7f1] p-4">
      <p className="text-[10px] font-bold text-[#77817d]">最终匹配分</p>
      <p className="mt-1 text-2xl font-semibold text-[#234e43]">{run.result.analysis.score}<span className="text-xs"> / 100</span></p>
    </div>}
    {(error || run?.error_message) && <p role="alert" className="mt-4 rounded-xl bg-[#fff1ea] px-3 py-2 text-xs text-[#9b4e37]">{error || run?.error_message}</p>}
    <button
      type="button"
      onClick={start}
      disabled={active}
      className="mt-5 w-full rounded-xl bg-[#234e43] py-2.5 text-xs font-bold text-white transition hover:bg-[#193c34] disabled:cursor-wait disabled:bg-[#8a9b95]"
    >{active ? "Copilot Agent 运行中…" : run?.status === "failed" || run?.status === "timeout" ? "重新运行 Copilot Agent" : "运行 Copilot Agent"}</button>
  </section>;
}
