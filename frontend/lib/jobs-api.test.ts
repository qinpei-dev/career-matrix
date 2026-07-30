import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { API_BASE_URL } from "./api.ts";
import { jobsApi } from "./jobs-api.ts";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("job list API encodes search, filters, sort, and pagination", async () => {
  let requestedUrl = "";
  globalThis.fetch = async (input) => {
    requestedUrl = String(input);
    return new Response(JSON.stringify([]), { status: 200 });
  };

  await jobsApi.list({
    query: "C++ 平台",
    sourceType: "extension",
    analysisStatus: "pending",
    sort: "title_asc",
    offset: 10,
    limit: 11,
  });

  const url = new URL(requestedUrl);
  assert.equal(`${url.origin}${url.pathname}`, `${API_BASE_URL}/api/v1/jobs`);
  assert.deepEqual(Object.fromEntries(url.searchParams), {
    query: "C++ 平台",
    source_type: "extension",
    analysis_status: "pending",
    sort: "title_asc",
    offset: "10",
    limit: "11",
  });
});

test("job update and delete use encoded user-scoped paths", async () => {
  const requests: Array<{ url: string; init?: RequestInit }> = [];
  globalThis.fetch = async (input, init) => {
    requests.push({ url: String(input), init });
    if (init?.method === "DELETE") return new Response(null, { status: 204 });
    return new Response(JSON.stringify({ id: "job/a" }), { status: 200 });
  };

  await jobsApi.update("job/a", { title: "Updated" });
  await jobsApi.delete("job/a");

  assert.equal(requests[0].url, `${API_BASE_URL}/api/v1/jobs/job%2Fa`);
  assert.equal(requests[0].init?.method, "PATCH");
  assert.equal(requests[0].init?.body, JSON.stringify({ title: "Updated" }));
  assert.equal(requests[1].url, `${API_BASE_URL}/api/v1/jobs/job%2Fa`);
  assert.equal(requests[1].init?.method, "DELETE");
});
