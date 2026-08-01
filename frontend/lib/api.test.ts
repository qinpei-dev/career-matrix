import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { API_BASE_URL, ApiError, api, apiFetch } from "./api.ts";
import { documentUploadNotice } from "./document-upload.ts";
import {
  shouldDeleteCachedTask,
  hasTaskPollingTimedOut,
  shouldPollAnalysisTask,
  TASK_POLL_TIMEOUT_MS,
} from "./analysis-task-recovery.ts";

const originalFetch = globalThis.fetch;
process.env.NEXT_PUBLIC_DEMO_AUTH_TOKEN = "test-web-token";

afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("apiFetch builds the API URL and returns JSON", async () => {
  let requestedUrl = "";
  let requestedInit: RequestInit | undefined;
  globalThis.fetch = async (input, init) => {
    requestedUrl = String(input);
    requestedInit = init;
    return new Response(JSON.stringify([{ id: "job-1" }]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  const result = await apiFetch<Array<{ id: string }>>("/api/v1/jobs");
  assert.equal(requestedUrl, `${API_BASE_URL}/api/v1/jobs`);
  assert.equal(new Headers(requestedInit?.headers).get("Authorization"), "Bearer test-web-token");
  assert.deepEqual(result, [{ id: "job-1" }]);
});

test("apiFetch surfaces FastAPI errors", async () => {
  globalThis.fetch = async () => new Response(
    JSON.stringify({ detail: "job not found" }),
    { status: 404, headers: { "Content-Type": "application/json" } },
  );

  await assert.rejects(
    () => apiFetch("/api/v1/jobs/missing"),
    (error) => error instanceof ApiError
      && error.status === 404
      && error.message === "job not found",
  );
});

test("job detail IDs are URL encoded", async () => {
  let requestedUrl = "";
  globalThis.fetch = async (input) => {
    requestedUrl = String(input);
    return new Response(JSON.stringify({ id: "a/b" }), { status: 200 });
  };

  await api.getJob("a/b");
  assert.equal(requestedUrl, `${API_BASE_URL}/api/v1/jobs/a%2Fb`);
});

test("createJob persists a manual or extension payload", async () => {
  let requestedInit: RequestInit | undefined;
  globalThis.fetch = async (_input, init) => {
    requestedInit = init;
    return new Response(JSON.stringify({ id: "job-2" }), { status: 201 });
  };
  const payload = {
    title: "Backend Engineer",
    company: "Example",
    description: "Build APIs",
    source_url: null,
    source_type: "manual",
  };

  await api.createJob(payload);

  assert.equal(requestedInit?.method, "POST");
  assert.equal(requestedInit?.body, JSON.stringify(payload));
});

test("createJob returns the idempotent creation status", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({
    id: "job-2",
    job_id: "job-2",
    status: "duplicate",
    message: "该岗位已保存",
  }), { status: 200 });

  const result = await api.createJob({
    title: "Backend Engineer",
    company: "Example",
    description: "Build APIs",
    source_url: "https://example.test/jobs/2",
    source_type: "manual",
  });

  assert.equal(result.status, "duplicate");
  assert.equal(result.job_id, "job-2");
});

test("analyzeJob posts to the saved-job workflow", async () => {
  let requestedUrl = "";
  let requestedMethod = "";
  globalThis.fetch = async (input, init) => {
    requestedUrl = String(input);
    requestedMethod = init?.method ?? "GET";
    return new Response(JSON.stringify({ id: "analysis-1", status: "completed" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await api.analyzeJob("job/1");
  assert.equal(requestedUrl, `${API_BASE_URL}/api/v1/jobs/job%2F1/analyze`);
  assert.equal(requestedMethod, "POST");
});

test("agent run APIs create and poll encoded runs", async () => {
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  globalThis.fetch = async (input, init) => {
    requests.push({ url: String(input), init });
    return new Response(JSON.stringify({ run_id: "run/1", status: "running" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await api.createAgentRun("job-1");
  await api.getAgentRun("run/1");

  assert.equal(requests[0].url, `${API_BASE_URL}/api/v1/agent/runs`);
  assert.equal(requests[0].init?.method, "POST");
  assert.equal(requests[0].init?.body, JSON.stringify({ job_id: "job-1" }));
  assert.equal(requests[1].url, `${API_BASE_URL}/api/v1/agent/runs/run%2F1`);
});

test("analysis task APIs create, run, retry, complete, and encode IDs", async () => {
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  globalThis.fetch = async (input, init) => {
    requests.push({ url: String(input), init });
    return new Response(JSON.stringify({
      task_id: "task/1", id: "task/1", status: "PENDING",
      current_step: "PENDING", progress: 0,
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  await api.createAnalysisTask("job-1");
  await api.getAnalysisTask("task/1");
  await api.getActiveAnalysisTask("job/1");
  await api.runAnalysisTask("task/1");
  await api.retryAnalysisTask("task/1");
  await api.completeAnalysisTask("task/1");

  assert.equal(requests[0].init?.body, JSON.stringify({ job_id: "job-1" }));
  assert.deepEqual(requests.slice(1).map((request) => request.url), [
    `${API_BASE_URL}/api/v1/analysis-tasks/task%2F1`,
    `${API_BASE_URL}/api/v1/analysis-tasks/active?job_id=job%2F1`,
    `${API_BASE_URL}/api/v1/analysis-tasks/task%2F1/run`,
    `${API_BASE_URL}/api/v1/analysis-tasks/task%2F1/retry`,
    `${API_BASE_URL}/api/v1/analysis-tasks/task%2F1/complete`,
  ]);
  assert.deepEqual(requests.slice(3).map((request) => request.init?.method), [
    "POST", "POST", "POST",
  ]);
});

test("analysis task recovery distinguishes missing tasks and polling states", () => {
  assert.equal(shouldDeleteCachedTask(new ApiError("missing", 404)), true);
  assert.equal(shouldDeleteCachedTask(new ApiError("server", 500)), false);
  const task = {
    id: "task-1", user_id: "user-1", job_id: "job-1",
    status: "ANALYZING" as const, current_step: "ANALYZING", progress: 30,
    retry_count: 0, max_retries: 3, error_code: null, error_message: null,
    result_id: null, started_at: null, completed_at: null,
    created_at: "", updated_at: "", is_running: false,
    claimed_at: null, lease_expires_at: null,
  };
  assert.equal(shouldPollAnalysisTask(task), true);
  assert.equal(shouldPollAnalysisTask({...task, status: "FAILED"}), false);
  assert.equal(hasTaskPollingTimedOut(1_000, 1_000 + TASK_POLL_TIMEOUT_MS - 1), false);
  assert.equal(hasTaskPollingTimedOut(1_000, 1_000 + TASK_POLL_TIMEOUT_MS), true);
});

test("workspace APIs search safely and persist settings", async () => {
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  globalThis.fetch = async (input, init) => {
    requests.push({ url: String(input), init });
    return new Response(JSON.stringify({ results: [], page_size: 20 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await api.getDashboard();
  await api.searchWorkspace("平台 / RAG", 20);
  await api.getNotifications(5);
  await api.getSettings();
  await api.updateSettings({
    display_name: "Candidate",
    page_size: 50,
    show_technical_details: true,
  });
  await api.getProviderStatuses();

  assert.deepEqual(requests.map((request) => request.url), [
    `${API_BASE_URL}/api/v1/workspace/dashboard`,
    `${API_BASE_URL}/api/v1/workspace/search?q=%E5%B9%B3%E5%8F%B0%20%2F%20RAG&limit=20`,
    `${API_BASE_URL}/api/v1/workspace/notifications?limit=5`,
    `${API_BASE_URL}/api/v1/workspace/settings`,
    `${API_BASE_URL}/api/v1/workspace/settings`,
    `${API_BASE_URL}/api/v1/workspace/providers`,
  ]);
  assert.equal(requests[4].init?.method, "PATCH");
  assert.equal(
    requests[4].init?.body,
    JSON.stringify({
      display_name: "Candidate",
      page_size: 50,
      show_technical_details: true,
    }),
  );
});

test("profile APIs generate a draft and create or update the current profile", async () => {
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  globalThis.fetch = async (input, init) => {
    requests.push({ url: String(input), init });
    return new Response(JSON.stringify({ id: "profile-1", name: "Candidate" }), {
      status: String(input).endsWith("/api/v1/profiles") ? 201 : 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const payload = {
    name: "Candidate",
    target_role: "Platform Engineer",
    summary: "Builds reliable services",
    skills: ["Python", "FastAPI"],
  };

  await api.draftProfileFromDocument("document-1");
  await api.createProfile(payload);
  await api.updateMyProfile(payload);

  assert.deepEqual(requests.map((request) => ({
    url: request.url,
    method: request.init?.method,
    body: request.init?.body,
  })), [
    {
      url: `${API_BASE_URL}/api/v1/profiles/draft-from-document`,
      method: "POST",
      body: JSON.stringify({ document_id: "document-1" }),
    },
    {
      url: `${API_BASE_URL}/api/v1/profiles`,
      method: "POST",
      body: JSON.stringify(payload),
    },
    {
      url: `${API_BASE_URL}/api/v1/profiles/me`,
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  ]);
});

test("document APIs use encoded user-scoped document paths", async () => {
  const requestedUrls: string[] = [];
  globalThis.fetch = async (input) => {
    requestedUrls.push(String(input));
    return new Response(JSON.stringify([]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await api.getDocuments();
  await api.getDocument("resume/a");
  await api.getDocumentChunks("resume/a");

  assert.deepEqual(requestedUrls, [
    `${API_BASE_URL}/api/v1/documents`,
    `${API_BASE_URL}/api/v1/documents/resume%2Fa`,
    `${API_BASE_URL}/api/v1/documents/resume%2Fa/chunks`,
  ]);
});

test("document upload and delete use multipart and DELETE", async () => {
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  globalThis.fetch = async (input, init) => {
    requests.push({ url: String(input), init });
    if (init?.method === "DELETE") return new Response(null, { status: 204 });
    return new Response(JSON.stringify({ id: "resume-1", status: "ready" }), { status: 201 });
  };

  await api.uploadDocument(new File(["resume"], "resume.pdf", { type: "application/pdf" }));
  await api.deleteDocument("resume/a");

  assert.equal(requests[0].url, `${API_BASE_URL}/api/v1/documents/upload`);
  assert.equal(requests[0].init?.method, "POST");
  assert.ok(requests[0].init?.body instanceof FormData);
  assert.equal(requests[1].url, `${API_BASE_URL}/api/v1/documents/resume%2Fa`);
  assert.equal(requests[1].init?.method, "DELETE");
});

test("duplicate document upload produces a duplicate notice", () => {
  const notice = documentUploadNotice({
    id: "resume-1",
    filename: "resume.pdf",
    file_type: "pdf",
    status: "ready",
    chunk_count: 2,
    created_at: "2026-07-21T00:00:00Z",
    updated_at: "2026-07-21T00:00:00Z",
    upload_status: "duplicate",
    is_duplicate: true,
    message: "backend duplicate message",
  });

  assert.deepEqual(notice, {
    message: "该简历版本已存在，无需重新解析",
    tone: "duplicate",
  });
});

test("semantic search posts query and top_k", async () => {
  let requestedUrl = "";
  let requestedInit: RequestInit | undefined;
  globalThis.fetch = async (input, init) => {
    requestedUrl = String(input);
    requestedInit = init;
    return new Response(JSON.stringify([]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await api.searchDocuments("FastAPI 后端经验", 3);

  assert.equal(requestedUrl, `${API_BASE_URL}/api/v1/retrieval/search`);
  assert.equal(requestedInit?.method, "POST");
  assert.equal(requestedInit?.body, JSON.stringify({ query: "FastAPI 后端经验", top_k: 3 }));
});
