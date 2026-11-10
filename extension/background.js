const NATIVE_HOST_NAME = "com.ai_job_copilot.service_control";
const ALLOWED_ACTIONS = new Set(["status", "start", "stop"]);

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "native-service-control" || !ALLOWED_ACTIONS.has(message.action)) {
    return false;
  }

  chrome.runtime.sendNativeMessage(
    NATIVE_HOST_NAME,
    { action: message.action },
    (response) => {
      if (chrome.runtime.lastError) {
        sendResponse({
          ok: false,
          state: "error",
          code: "native_host_unavailable",
          message: "Native Messaging Host 尚未安装",
        });
        return;
      }
      const validStates = new Set(["stopped", "starting", "running", "stopping", "error"]);
      if (!response || typeof response.ok !== "boolean" || !validStates.has(response.state)) {
        sendResponse({ ok: false, state: "error", message: "本地连接组件响应无效" });
        return;
      }
      sendResponse({ ok: response.ok, state: response.state, message: String(response.message || "") });
    },
  );
  return true;
});

// BOSS 直聘 auto capture: boss.js reports the job the user is viewing; this
// worker saves it to the local backend. Nothing is ever sent to the job site.
const API_BASE = "http://127.0.0.1:8000";

async function startAnalysis(jobId, headers) {
  const created = await fetch(`${API_BASE}/api/v1/analysis-tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ job_id: jobId }),
  });
  if (!created.ok) return;
  const { task_id: taskId } = await created.json();
  // Not awaited: the backend finishes the run even if this worker is suspended.
  fetch(`${API_BASE}/api/v1/analysis-tasks/${encodeURIComponent(taskId)}/run`, {
    method: "POST",
    headers,
  }).catch(() => {});
}

async function captureBossJob(job) {
  const settings = await chrome.storage.local.get({
    bossAutoCapture: false,
    bossAutoAnalyze: true,
    bossCapturedCount: 0,
    demoToken: "",
  });
  if (!settings.bossAutoCapture) return { ok: false, reason: "disabled" };
  if (!settings.demoToken) {
    chrome.action.setBadgeText({ text: "!" });
    return { ok: false, reason: "missing_token" };
  }
  const headers = { Authorization: `Bearer ${settings.demoToken}` };
  try {
    const response = await fetch(`${API_BASE}/api/v1/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({
        title: String(job.title),
        company: job.company ?? null,
        description: String(job.description),
        source_url: String(job.source_url),
        source_type: "zhipin",
        salary: job.salary ?? null,
        location: job.location ?? null,
        experience: job.experience ?? null,
        education: job.education ?? null,
      }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const saved = await response.json();
    if (saved.status === "created") {
      const count = settings.bossCapturedCount + 1;
      await chrome.storage.local.set({ bossCapturedCount: count });
      chrome.action.setBadgeText({ text: String(count) });
      if (settings.bossAutoAnalyze) await startAnalysis(saved.job_id, headers);
    }
    return { ok: true, status: saved.status };
  } catch (error) {
    chrome.action.setBadgeText({ text: "!" });
    return { ok: false, reason: "backend_unavailable" };
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "boss-job-captured" || !message.job) return false;
  if (sender.id !== chrome.runtime.id || !sender.url?.startsWith("https://www.zhipin.com/")) {
    return false;
  }
  captureBossJob(message.job).then(sendResponse);
  return true;
});
