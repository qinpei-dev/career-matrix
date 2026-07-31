import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { API_BASE_URL } from "./api.ts";
import {
  canGenerate,
  comparisonLabel,
  tailoredResumesApi,
} from "./tailored-resumes-api.ts";

const originalFetch = globalThis.fetch;
process.env.NEXT_PUBLIC_DEMO_AUTH_TOKEN = "test-web-token";

afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("tailored resume API covers create generate save finalize delete and authenticated download", async () => {
  const requests: Array<{ url: string; method: string; body?: string; init?: RequestInit }> = [];
  globalThis.fetch = async (input, init) => {
    requests.push({
      url: String(input),
      method: init?.method ?? "GET",
      body: typeof init?.body === "string" ? init.body : undefined,
      init,
    });
    if (init?.method === "DELETE") return new Response(null, { status: 204 });
    return new Response(JSON.stringify({ id: "version/1", status: "GENERATED" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await tailoredResumesApi.create({ job_id: "job/1", source_document_id: "doc/1" });
  await tailoredResumesApi.list("job/1");
  await tailoredResumesApi.get("version/1");
  await tailoredResumesApi.generate("version/1");
  await tailoredResumesApi.update("version/1", { skills: ["Python"] });
  await tailoredResumesApi.finalize("version/1");
  await tailoredResumesApi.delete("version/1");
  const downloaded = await tailoredResumesApi.downloadDocx("version/1");

  assert.deepEqual(requests.map(({ url, method }) => ({ url, method })), [
    { url: `${API_BASE_URL}/api/v1/tailored-resumes`, method: "POST" },
    { url: `${API_BASE_URL}/api/v1/tailored-resumes?job_id=job%2F1`, method: "GET" },
    { url: `${API_BASE_URL}/api/v1/tailored-resumes/version%2F1`, method: "GET" },
    { url: `${API_BASE_URL}/api/v1/tailored-resumes/version%2F1/generate`, method: "POST" },
    { url: `${API_BASE_URL}/api/v1/tailored-resumes/version%2F1`, method: "PATCH" },
    { url: `${API_BASE_URL}/api/v1/tailored-resumes/version%2F1/finalize`, method: "POST" },
    { url: `${API_BASE_URL}/api/v1/tailored-resumes/version%2F1`, method: "DELETE" },
    { url: `${API_BASE_URL}/api/v1/tailored-resumes/version%2F1/export.docx`, method: "GET" },
  ]);
  assert.match(requests[4].body ?? "", /Python/);
  assert.equal(requests[7].url, `${API_BASE_URL}/api/v1/tailored-resumes/version%2F1/export.docx`);
  assert.equal(downloaded instanceof Blob, true);
  assert.equal(
    new Headers(requests[7].init?.headers).get("Authorization"),
    "Bearer test-web-token",
  );
});

test("busy guard and comparison labels are deterministic", () => {
  assert.equal(canGenerate("DRAFT", false), true);
  assert.equal(canGenerate("FAILED", false), true);
  assert.equal(canGenerate("DRAFT", true), false);
  assert.equal(canGenerate("GENERATED", false), false);
  assert.equal(canGenerate("FINALIZED", false), true);
  assert.equal(comparisonLabel("Python FastAPI", "Python FastAPI"), "保留");
  assert.equal(comparisonLabel("Python FastAPI", "FastAPI Python"), "调整顺序");
  assert.equal(comparisonLabel("Python FastAPI", ""), "删除冗余");
  assert.equal(comparisonLabel("Python", "Python APIs"), "改写");
});
