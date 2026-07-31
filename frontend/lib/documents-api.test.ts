import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { API_BASE_URL } from "./api.ts";
import { documentsApi, uploadDocument } from "./documents-api.ts";

const originalFetch = globalThis.fetch;
const originalXMLHttpRequest = globalThis.XMLHttpRequest;
process.env.NEXT_PUBLIC_DEMO_AUTH_TOKEN = "test-web-token";

afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.XMLHttpRequest = originalXMLHttpRequest;
});

test("document upload attaches Demo Auth to XMLHttpRequest", async () => {
  const headers = new Map<string, string>();

  class FakeXMLHttpRequest {
    status = 201;
    responseText = JSON.stringify({ id: "resume-1", upload_status: "created" });
    upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null };
    onerror: (() => void) | null = null;
    onload: (() => void) | null = null;

    open() {}
    setRequestHeader(name: string, value: string) { headers.set(name, value); }
    send() { this.onload?.(); }
  }

  globalThis.XMLHttpRequest = FakeXMLHttpRequest as unknown as typeof XMLHttpRequest;
  await uploadDocument(
    new File(["resume"], "resume.pdf", { type: "application/pdf" }),
    () => undefined,
  );

  assert.equal(headers.get("Authorization"), "Bearer test-web-token");
  assert.equal(headers.get("Accept"), "application/json");
});

test("document management APIs encode IDs and expose retry", async () => {
  const requests: Array<{ url: string; method: string }> = [];
  globalThis.fetch = async (input, init) => {
    requests.push({ url: String(input), method: init?.method ?? "GET" });
    if (init?.method === "DELETE") return new Response(null, { status: 204 });
    return new Response(JSON.stringify({ id: "resume/1" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await documentsApi.get("resume/1");
  await documentsApi.chunks("resume/1");
  await documentsApi.retry("resume/1");
  await documentsApi.delete("resume/1");

  assert.deepEqual(requests, [
    { url: `${API_BASE_URL}/api/v1/documents/resume%2F1`, method: "GET" },
    { url: `${API_BASE_URL}/api/v1/documents/resume%2F1/chunks`, method: "GET" },
    { url: `${API_BASE_URL}/api/v1/documents/resume%2F1/retry`, method: "POST" },
    { url: `${API_BASE_URL}/api/v1/documents/resume%2F1`, method: "DELETE" },
  ]);
});
