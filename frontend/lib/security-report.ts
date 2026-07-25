export type RegressionStatus = "PASS" | "FAIL" | "NOT_VERIFIED";

export interface SecurityCheck {
  id: string;
  name: string;
  status: RegressionStatus;
  detail: string;
}

export interface SecurityTestReport {
  test_name: string;
  scope: string;
  malicious_input_summary: string;
  analysis_result: Record<string, unknown>;
  evidence: Array<Record<string, unknown>>;
  checks: SecurityCheck[];
  overall_status: RegressionStatus;
  tool_names: string[];
  trace: string[];
}

const sensitivePatterns = [
  /TEST_SECRET_DO_NOT_EXPOSE_[A-Za-z0-9_-]+/gi,
  /TEST_SECRET_CANARY_[A-Za-z0-9_-]+/gi,
  /\bsk-[A-Za-z0-9_-]{12,}\b/gi,
  /\b(bearer\s+)[A-Za-z0-9._~+/=-]{8,}/gi,
  /\b(api[_ -]?key|token|secret|password|authorization)(\s*[:=]\s*)([^\s,;"']{4,})/gi,
];

export function redactForDisplay(value: string): string {
  return value
    .replace(/\bauthorization\s*[:=]\s*bearer\s+[A-Za-z0-9._~+/=-]{8,}/gi, "Authorization: [REDACTED]")
    .replace(sensitivePatterns[0], "[REDACTED]")
    .replace(sensitivePatterns[1], "[REDACTED]")
    .replace(sensitivePatterns[2], "[REDACTED]")
    .replace(sensitivePatterns[3], "$1[REDACTED]")
    .replace(sensitivePatterns[4], "$1$2[REDACTED]");
}

export function deriveOverallStatus(checks: SecurityCheck[]): RegressionStatus {
  if (checks.some((check) => check.status === "FAIL")) return "FAIL";
  if (checks.some((check) => check.status === "PASS")) return "PASS";
  return "NOT_VERIFIED";
}

export function redactUnknown(value: unknown): unknown {
  if (typeof value === "string") return redactForDisplay(value);
  if (Array.isArray(value)) return value.map(redactUnknown);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, redactUnknown(item)]),
    );
  }
  return value;
}

export function validateSecurityReport(report: SecurityTestReport): SecurityTestReport {
  return {
    ...report,
    overall_status: deriveOverallStatus(report.checks),
    test_name: redactForDisplay(report.test_name),
    scope: redactForDisplay(report.scope),
    malicious_input_summary: redactForDisplay(report.malicious_input_summary),
    checks: report.checks.map((check) => ({
      ...check,
      name: redactForDisplay(check.name),
      detail: redactForDisplay(check.detail),
    })),
    analysis_result: redactUnknown(report.analysis_result) as Record<string, unknown>,
    evidence: redactUnknown(report.evidence) as Array<Record<string, unknown>>,
    tool_names: report.tool_names.map(redactForDisplay),
    trace: report.trace.map(redactForDisplay),
  };
}
