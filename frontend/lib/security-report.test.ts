import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  deriveOverallStatus,
  redactForDisplay,
  validateSecurityReport,
  type SecurityTestReport,
} from "./security-report.ts";

const passing = [
  { id: "one", name: "one", status: "PASS" as const, detail: "ok" },
  { id: "two", name: "two", status: "PASS" as const, detail: "ok" },
];

test("real checks determine PASS, failures determine FAIL, and unknowns remain explicit", () => {
  assert.equal(deriveOverallStatus(passing), "PASS");
  assert.equal(deriveOverallStatus([...passing, { id: "three", name: "three", status: "FAIL", detail: "failed" }]), "FAIL");
  assert.equal(deriveOverallStatus([{ id: "external", name: "external", status: "NOT_VERIFIED", detail: "mock only" }]), "NOT_VERIFIED");
  assert.equal(deriveOverallStatus([]), "NOT_VERIFIED");
});

test("display text and error details are redacted", () => {
  const secret = ["TEST_SECRET", "CANARY", "12345"].join("_");
  assert.equal(redactForDisplay(`error: ${secret}`), "error: [REDACTED]");
  assert.equal(redactForDisplay("Authorization: Bearer abcdefghijklmnop"), "Authorization: [REDACTED]");
});

test("backend PASS cannot override a failing real check", () => {
  const report: SecurityTestReport = {
    test_name: "test", scope: "regression", malicious_input_summary: "summary",
    analysis_result: {}, evidence: [],
    checks: [{ id: "failed", name: "failed", status: "FAIL", detail: "no" }],
    overall_status: "PASS", tool_names: [], trace: [],
  };
  assert.equal(validateSecurityReport(report).overall_status, "FAIL");
});

test("nested result, trace, and evidence canaries are redacted before render", () => {
  const secret = ["TEST_SECRET", "CANARY", "12345"].join("_");
  const report: SecurityTestReport = {
    test_name: "Prompt Injection Regression Test",
    scope: "Mock model; external model is NOT VERIFIED.",
    malicious_input_summary: "summary",
    analysis_result: { reasoning: [`leak ${secret}`] },
    evidence: [{ content: secret }],
    checks: [{ id: "secret", name: "secret", status: "PASS", detail: secret }],
    overall_status: "PASS",
    tool_names: ["save_analysis_result"],
    trace: [secret],
  };
  const serialized = JSON.stringify(validateSecurityReport(report));
  assert.doesNotMatch(serialized, /TEST_SECRET_CANARY_12345/);
  assert.match(serialized, /\[REDACTED\]/);
});

test("runner exposes a busy state and disables duplicate execution", () => {
  const source = fs.readFileSync(
    new URL("../app/security-tests/untrusted-content/security-test-runner.tsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /if \(busy\) return/);
  assert.match(source, /disabled=\{busy\}/);
  assert.match(source, /aria-busy=\{busy\}/);
  assert.match(source, /NOT VERIFIED/);
  assert.match(source, /Prompt Injection Regression Test/);
});
