"use client";

import { useState } from "react";
import { api } from "../../../lib/api";
import {
  type SecurityTestReport,
  redactForDisplay,
  validateSecurityReport,
} from "../../../lib/security-report";

export function SecurityTestRunner() {
  const [report, setReport] = useState<SecurityTestReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function runTest() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      setReport(validateSecurityReport(await api.runUntrustedContentSecurityTest()));
    } catch (caught) {
      setReport(null);
      setError(redactForDisplay(caught instanceof Error ? caught.message : "安全测试执行失败"));
    } finally {
      setBusy(false);
    }
  }

  function statusClass(status: "PASS" | "FAIL" | "NOT_VERIFIED") {
    if (status === "PASS") return "border-[#a7f3d0] bg-[#f1f5f9] text-[#2563eb]";
    if (status === "FAIL") return "border-[#fca5a5] bg-[#fef2f2] text-[#b91c1c]";
    return "border-[#fde68a] bg-[#fffbeb] text-[#92400e]";
  }

  return (
    <div className="grid gap-5">
      <section className="rounded-xl border border-[#e2e8f0] bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold text-[#1d4ed8]">真实本地代码路径 · Mock LLM / Embedding</p>
            <h2 className="mt-2 text-xl font-semibold">Prompt Injection Regression Test</h2>
          </div>
          <button type="button" onClick={runTest} disabled={busy} aria-busy={busy}
            className="rounded-xl bg-[#2563eb] px-5 py-3 text-sm font-semibold text-white disabled:cursor-wait disabled:opacity-60">
            {busy ? "测试执行中…" : "运行完整测试"}
          </button>
        </div>
        <p className="mt-4 rounded-xl bg-[#fffbeb] px-4 py-3 text-sm text-[#92400e]">
          恶意输入摘要：{report?.malicious_input_summary ?? "规则覆盖、文件读取、密钥泄露、自动发送、越权与数据外传指令。"}
        </p>
        <p className="mt-3 text-xs leading-5 text-[#64748b]">
          {report?.scope ?? "此页面是生产代码路径回归测试，不构成完整安全证明，也不验证真实外部模型。"}
        </p>
        {error && <p role="alert" className="mt-4 rounded-xl bg-[#fef2f2] px-4 py-3 text-sm text-[#b91c1c]">{error}</p>}
      </section>

      {report && <>
        <section className={`rounded-xl border p-6 ${statusClass(report.overall_status)}`}>
          <p className="text-xs font-semibold tracking-[.16em]">总体结果</p>
          <p className="mt-2 text-3xl font-semibold">回归状态：{report.overall_status}</p>
          <p className="mt-2 text-xs">PASS 代表真实本地代码路径断言通过；NOT VERIFIED 代表需要真实外部模型或人工验证。</p>
        </section>
        <section className="rounded-xl border border-[#e2e8f0] bg-white p-6">
          <h3 className="text-base font-semibold">检查明细</h3>
          <div className="mt-4 grid gap-3">
            {report.checks.map((check) => <article key={check.id} className="rounded-xl border border-[#e2e8f0] p-4">
              <div className="flex items-center justify-between gap-4">
                <strong className="text-sm">{check.name}</strong>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusClass(check.status)}`}>{check.status}</span>
              </div>
              <p className="mt-2 text-xs leading-5 text-[#64748b]">{check.detail}</p>
            </article>)}
          </div>
        </section>
        <section className="rounded-xl border border-[#e2e8f0] bg-white p-6">
          <h3 className="text-base font-semibold">实际分析结果</h3>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            {Object.entries(report.analysis_result).map(([key, value]) => <div key={key} className="rounded-xl bg-[#f1f5f9] p-3">
              <dt className="text-xs font-semibold text-[#64748b]">{key}</dt>
              <dd className="mt-1 break-words">{redactForDisplay(Array.isArray(value) ? value.join("、") : String(value))}</dd>
            </div>)}
          </dl>
        </section>
        <section className="rounded-xl border border-[#e2e8f0] bg-white p-6">
          <h3 className="text-base font-semibold">Trace / Evidence</h3>
          <p className="mt-3 break-words rounded-xl bg-[#f1f5f9] p-3 text-xs leading-5">
            Trace：{report.trace.map(redactForDisplay).join(" → ")}
          </p>
          <pre className="mt-3 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-[#f1f5f9] p-3 text-xs leading-5">
            {redactForDisplay(JSON.stringify(report.evidence, null, 2))}
          </pre>
        </section>
      </>}
    </div>
  );
}
