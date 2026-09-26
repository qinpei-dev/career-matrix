const healthCheckButton = document.querySelector("#health-check");
const readJobButton = document.querySelector("#read-job");
const analyzeJobButton = document.querySelector("#analyze-job");
const saveJobButton = document.querySelector("#save-job");
const saveAndAnalyzeButton = document.querySelector("#save-and-analyze");
const demoToken = document.querySelector("#demo-token");
const analyzeLabel = document.querySelector("#analyze-label");
const analyzeSpinner = document.querySelector("#analyze-spinner");
const backendStatus = document.querySelector("#backend-status");
const pageTitle = document.querySelector("#page-title");
const pageUrl = document.querySelector("#page-url");
const readSource = document.querySelector("#read-source");
const jobDescription = document.querySelector("#job-description");
const candidateProfile = document.querySelector("#candidate-profile");
const analysisResult = document.querySelector("#analysis-result");
const greetingSection = document.querySelector("#greeting-section");
const greetingTextarea = document.querySelector("#analysis-greeting");
const copyGreetingButton = document.querySelector("#copy-greeting");
const result = document.querySelector("#result");
const serviceStatus = document.querySelector("#service-status");
const serviceControlButton = document.querySelector("#service-control");
const serviceControlLabel = document.querySelector("#service-control-label");
const serviceSpinner = document.querySelector("#service-spinner");
let jobDescriptionEdited = false;
let analysisInProgress = false;
let saveInProgress = false;
let serviceControlInProgress = false;
let copyFeedbackTimer;
let localServiceState = "unknown";
let nativeHostInstalled = null;

const HEALTH_URL = "http://127.0.0.1:8000/health";
const NATIVE_INSTALL_MESSAGE =
  "首次使用需要安装本地连接组件，请运行项目目录中的 install_native_host.bat。";

const CANDIDATE_PROFILE_STORAGE_KEY = "aiJobCopilot.candidateProfile";
const DEFAULT_CANDIDATE_PROFILE =
  "大数据专业学生，掌握 Python、FastAPI、Git，使用过 Linux，完成过 AI Agent 项目。" +
  "了解 SQL，Docker 处于基础学习阶段，暂无正式开发实习经历。";

const SCORE_BREAKDOWN_LABELS = {
  core_skills: "核心技能",
  preferred_skills: "优先技能",
  project_experience: "项目经验",
  education_background: "教育背景",
  work_experience: "工作经验",
};

function asArray(value) {
  return Array.isArray(value) ? value.filter((item) => item !== null && item !== undefined) : [];
}

function safeText(value, fallback = "") {
  return value === null || value === undefined ? fallback : String(value);
}

function loadCandidateProfile() {
  try {
    candidateProfile.value =
      localStorage.getItem(CANDIDATE_PROFILE_STORAGE_KEY) ?? DEFAULT_CANDIDATE_PROFILE;
  } catch (error) {
    console.error("Loading candidate profile failed:", error);
    candidateProfile.value = DEFAULT_CANDIDATE_PROFILE;
  }
}

function saveCandidateProfile() {
  try {
    localStorage.setItem(CANDIDATE_PROFILE_STORAGE_KEY, candidateProfile.value);
  } catch (error) {
    console.error("Saving candidate profile failed:", error);
  }
}

function showStatus(message, type = "info") {
  result.className = "status-message";
  if (message) {
    result.classList.add(type);
  }
  result.textContent = message;
}

function setBackendStatus(label, type = "idle") {
  backendStatus.className = `backend-status status-${type}`;
  const labelElement = backendStatus.querySelector("span:last-child");
  if (labelElement) {
    labelElement.textContent = label;
  }
}

function setServiceState(state, message = "") {
  const labels = {
    unknown: "未检测",
    uninstalled: "尚未安装本地连接组件",
    stopped: "已停止",
    starting: "正在启动",
    running: "运行中",
    stopping: "正在停止",
    error: "启动失败",
  };
  localServiceState = state;
  serviceStatus.textContent = message || labels[state] || labels.error;
  serviceStatus.className = "service-status";
  if (state === "running") serviceStatus.classList.add("status-success");
  if (["stopped", "starting", "stopping"].includes(state)) {
    serviceStatus.classList.add("status-warning");
  }
  if (["uninstalled", "error"].includes(state)) serviceStatus.classList.add("status-error");

  const busy = state === "starting" || state === "stopping";
  serviceSpinner.hidden = !busy;
  serviceControlButton.disabled = busy || state === "unknown" || state === "uninstalled";
  serviceControlLabel.textContent = state === "running" ? "停止本地服务" : "启动本地服务";
}

async function checkBackendHealth() {
  try {
    const response = await fetch(HEALTH_URL);
    if (!response.ok) return false;
    const data = await response.json();
    return data.status === "ok";
  } catch (_error) {
    return false;
  }
}

function sendNativeControl(action) {
  return new Promise((resolve) => {
    if (!chrome.runtime?.sendMessage) {
      resolve({ ok: false, state: "error", code: "native_host_unavailable" });
      return;
    }
    chrome.runtime.sendMessage({ type: "native-service-control", action }, (response) => {
      if (chrome.runtime.lastError || !response) {
        resolve({ ok: false, state: "error", code: "native_host_unavailable" });
        return;
      }
      resolve(response);
    });
  });
}

async function detectServiceStatus() {
  if (await checkBackendHealth()) {
    nativeHostInstalled = true;
    setServiceState("running");
    setBackendStatus("后端正常", "success");
    return "running";
  }

  setBackendStatus("后端未运行", "error");
  const response = await sendNativeControl("status");
  if (response.code === "native_host_unavailable") {
    nativeHostInstalled = false;
    setServiceState("uninstalled");
    return "uninstalled";
  }
  nativeHostInstalled = true;
  const state = response.ok && ["stopped", "running"].includes(response.state)
    ? response.state
    : "error";
  setServiceState(state, response.message || "");
  return state;
}

function wait(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function pollHealth(expectedRunning, attempts, interval) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const running = await checkBackendHealth();
    if (running === expectedRunning) return true;
    if (attempt + 1 < attempts) await wait(interval);
  }
  return false;
}

async function startLocalService() {
  setServiceState("starting");
  const response = await sendNativeControl("start");
  if (response.code === "native_host_unavailable") {
    nativeHostInstalled = false;
    setServiceState("uninstalled");
    showStatus(NATIVE_INSTALL_MESSAGE, "error");
    return false;
  }
  nativeHostInstalled = true;
  if (!response.ok) {
    setServiceState("error", response.message || "本地服务启动失败");
    showStatus(response.message || "本地服务启动失败，请检查后端日志", "error");
    return false;
  }
  if (await pollHealth(true, 30, 400)) {
    setServiceState("running");
    setBackendStatus("后端正常", "success");
    return true;
  }
  setServiceState("error", "启动失败或健康检查超时");
  showStatus("本地服务未能在 12 秒内通过健康检查", "error");
  return false;
}

async function stopLocalService() {
  setServiceState("stopping");
  const response = await sendNativeControl("stop");
  if (response.code === "native_host_unavailable") {
    nativeHostInstalled = false;
    setServiceState("uninstalled");
    showStatus(NATIVE_INSTALL_MESSAGE, "error");
    return false;
  }
  nativeHostInstalled = true;
  if (!response.ok) {
    setServiceState("error", response.message || "本地服务停止失败");
    showStatus(response.message || "本地服务停止失败，请手动检查", "error");
    return false;
  }
  if (await pollHealth(false, 25, 400)) {
    setServiceState("stopped");
    setBackendStatus("后端未运行", "error");
    showStatus("本地服务已停止", "success");
    return true;
  }
  setServiceState("error", "停止确认超时");
  showStatus("本地服务未能在 10 秒内停止，请手动检查", "error");
  return false;
}

async function ensureServiceForAnalysis() {
  console.debug("[service-control] analysis auto-start requested");
  analyzeLabel.textContent = "正在启动本地服务……";
  showStatus("正在启动本地服务，成功后将继续分析……", "loading");
  return startLocalService();
}

function setLoadingState(isLoading) {
  analysisInProgress = isLoading;
  analyzeJobButton.disabled = isLoading;
  analyzeSpinner.hidden = !isLoading;
  analyzeLabel.textContent = isLoading ? "正在分析岗位……" : "分析岗位";
}

function currentJobPayload() {
  const title = pageTitle.textContent.trim();
  const description = jobDescription.value.trim();
  if (!title || title === "尚未读取") throw new Error("岗位标题为空，请先读取当前岗位");
  if (!description) throw new Error("岗位内容为空，请先读取或填写 JD");
  return {
    title,
    company: null,
    description,
    source_url: pageUrl.textContent.trim() || null,
    source_type: "extension",
  };
}

function demoAuthorizationHeaders() {
  const token = demoToken.value.trim();
  if (!token || /\s/.test(token)) {
    throw new Error("请先填写有效的本地 Demo Token");
  }
  return { Authorization: `Bearer ${token}` };
}

async function saveCurrentJob({ analyze = false } = {}) {
  if (saveInProgress || analysisInProgress) return;
  saveInProgress = true;
  saveJobButton.disabled = true;
  saveAndAnalyzeButton.disabled = true;
  try {
    const payload = currentJobPayload();
    const authHeaders = demoAuthorizationHeaders();
    if (!(await checkBackendHealth())) {
      showStatus("后端未连接，无法保存岗位", "error");
      return;
    }
    showStatus(analyze ? "正在保存岗位并分析……" : "正在保存岗位……", "loading");
    const savedResponse = await fetch("http://127.0.0.1:8000/api/v1/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify(payload),
    });
    if (!savedResponse.ok) throw new Error(`保存岗位失败（HTTP ${savedResponse.status}）`);
    const savedJob = await savedResponse.json();
    if (savedJob.status === "duplicate") {
      showStatus("该岗位已保存", "info");
      return;
    }
    if (!analyze) {
      showStatus("岗位保存成功", "success");
      return;
    }
    const analysisResponse = await fetch(
      `http://127.0.0.1:8000/api/v1/jobs/${encodeURIComponent(savedJob.job_id)}/analyze`,
      { method: "POST", headers: authHeaders },
    );
    if (!analysisResponse.ok) throw new Error(`岗位已保存，但分析失败（HTTP ${analysisResponse.status}）`);
    const savedAnalysis = await analysisResponse.json();
    renderAnalysis(savedAnalysis.result_json || {});
    showStatus("岗位已保存，分析结果已写入数据库", "success");
  } catch (error) {
    showStatus(error instanceof Error ? error.message : "保存岗位失败", "error");
  } finally {
    saveInProgress = false;
    saveJobButton.disabled = false;
    saveAndAnalyzeButton.disabled = false;
  }
}

function renderSkillTags(elementId, sectionId, items) {
  const list = document.querySelector(`#${elementId}`);
  const section = document.querySelector(`#${sectionId}`);
  const values = asArray(items);
  list.replaceChildren();
  section.hidden = values.length === 0;

  for (const item of values) {
    const listItem = document.createElement("li");
    listItem.textContent = safeText(item);
    list.append(listItem);
  }
}

function renderListSection(elementId, sectionId, items) {
  const list = document.querySelector(`#${elementId}`);
  const section = document.querySelector(`#${sectionId}`);
  const values = asArray(items);
  list.replaceChildren();
  section.hidden = values.length === 0;

  for (const item of values) {
    const listItem = document.createElement("li");
    listItem.textContent = safeText(item);
    list.append(listItem);
  }
}

function getScoreLabel(score) {
  if (score >= 80) return "匹配度较高";
  if (score >= 60) return "部分匹配";
  if (score >= 40) return "存在明显差距";
  return "当前匹配较低";
}

function renderScore(score) {
  const numericScore = Number(score);
  const normalizedScore = Number.isFinite(numericScore)
    ? Math.min(100, Math.max(0, numericScore))
    : 0;
  const scoreElement = document.querySelector("#analysis-score");
  scoreElement.replaceChildren();
  scoreElement.append(document.createTextNode(`${normalizedScore} `));
  const suffix = document.createElement("small");
  suffix.textContent = "/ 100";
  scoreElement.append(suffix);
  document.querySelector("#score-label").textContent = getScoreLabel(normalizedScore);
}

function renderScoreBreakdown(scoreBreakdown) {
  const section = document.querySelector("#score-breakdown-section");
  const container = document.querySelector("#score-breakdown");
  container.replaceChildren();

  if (!scoreBreakdown || typeof scoreBreakdown !== "object") {
    section.hidden = true;
    return;
  }

  for (const [key, label] of Object.entries(SCORE_BREAKDOWN_LABELS)) {
    const entry = scoreBreakdown[key];
    if (!entry || typeof entry !== "object") continue;

    const item = document.createElement("section");
    item.className = "breakdown-item";
    const title = document.createElement("p");
    title.className = "breakdown-title";
    const name = document.createElement("span");
    name.textContent = label;
    const score = document.createElement("span");
    score.textContent = safeText(entry.score, "—");
    title.append(name, score);
    item.append(title);

    if (entry.reason) {
      const reason = document.createElement("p");
      reason.className = "breakdown-reason";
      reason.textContent = safeText(entry.reason);
      item.append(reason);
    }
    if (entry.weight !== null && entry.weight !== undefined && entry.weight !== "") {
      const weight = document.createElement("p");
      weight.className = "breakdown-meta";
      weight.textContent = `权重 ${safeText(entry.weight)}`;
      item.append(weight);
    }
    container.append(item);
  }

  section.hidden = container.children.length === 0;
}

function renderAnalysis(analysis = {}) {
  renderScore(analysis.score);
  document.querySelector("#analysis-summary").textContent = safeText(
    analysis.summary,
    "暂无摘要",
  );
  renderSkillTags("matched-skills", "matched-skills-section", analysis.matched_skills);
  renderSkillTags("partial-skills", "partial-skills-section", analysis.partial_skills);
  renderSkillTags("missing-skills", "missing-skills-section", analysis.missing_skills);
  renderSkillTags("unverified-skills", "unverified-skills-section", analysis.unverified_skills);
  renderListSection("learning-plan", "learning-plan-section", analysis.learning_plan);
  renderListSection("analysis-reasoning", "reasoning-section", analysis.reasoning);
  renderScoreBreakdown(analysis.score_breakdown);

  const confidence = Number(analysis.confidence);
  document.querySelector("#analysis-confidence").textContent = Number.isFinite(confidence)
    ? `参考置信度 ${Math.round(confidence * 100)}%`
    : "";

  const greeting = safeText(analysis.greeting).trim();
  greetingTextarea.value = greeting;
  greetingSection.hidden = !greeting;
  copyGreetingButton.disabled = !greeting;
  analysisResult.hidden = false;
}

function setReadSource(source, successful) {
  const labels = {
    selection: "当前选中文本",
    "smart-job-detail": "智能岗位详情识别",
    main: "页面主要内容",
    article: "页面主要内容",
    "role-main": "页面主要内容",
    body: "整页正文回退",
  };
  readSource.textContent = labels[source] || (successful ? "页面内容" : "读取失败");
}

async function readCurrentJob({ automatic = false } = {}) {
  readJobButton.disabled = true;
  showStatus("正在读取当前网页……", "loading");

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error("No active tab is available");

    const injectionResults = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractJobContent,
    });
    const page = injectionResults[0]?.result;
    if (!page) throw new Error("The page did not return readable content");

    console.debug("Job content extraction", {
      source: page.source,
      candidateCount: page.debug?.candidateCount ?? 0,
      score: page.debug?.score ?? null,
      textLength: page.debug?.textLength ?? page.text.length,
    });
    pageTitle.textContent = page.title || "未获取到页面标题";
    pageUrl.textContent = page.url || "未获取到页面 URL";
    pageUrl.title = page.url || "";
    setReadSource(page.source, Boolean(page.text));

    if (automatic && jobDescriptionEdited) {
      showStatus("已保留手动编辑的岗位 JD", "success");
      return;
    }

    jobDescription.value = page.text;
    jobDescriptionEdited = false;
    if (!page.text) {
      showStatus("岗位内容为空，请先读取或填写 JD", "warning");
    } else if (page.source === "selection") {
      showStatus("已读取当前选中的岗位内容", "success");
    } else if (page.source === "smart-job-detail") {
      showStatus("已智能识别岗位详情，请检查后再分析", "success");
    } else if (["main", "article", "role-main"].includes(page.source)) {
      showStatus("已自动读取页面主要内容", "success");
    } else {
      showStatus("未准确识别岗位详情，已读取整页内容，请手动删除无关内容", "warning");
    }
  } catch (error) {
    console.error("Reading the active page failed:", error);
    setReadSource("", false);
    showStatus("无法读取当前网页，请确认页面允许扩展访问后重试", "error");
  } finally {
    readJobButton.disabled = false;
  }
}

async function copyGreeting() {
  const text = greetingTextarea.value.trim();
  if (!text) {
    copyGreetingButton.disabled = true;
    showStatus("暂无可复制的打招呼文案", "warning");
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    clearTimeout(copyFeedbackTimer);
    copyGreetingButton.textContent = "已复制";
    showStatus("打招呼文案已复制", "success");
    copyFeedbackTimer = setTimeout(() => {
      copyGreetingButton.textContent = "复制打招呼文案";
    }, 1800);
  } catch (error) {
    console.error("Copying greeting failed:", error);
    showStatus("复制失败，请手动选择文案复制", "error");
  }
}

loadCandidateProfile();
candidateProfile.addEventListener("input", saveCandidateProfile);
jobDescription.addEventListener("input", () => {
  jobDescriptionEdited = true;
});
greetingTextarea.addEventListener("input", () => {
  copyGreetingButton.disabled = !greetingTextarea.value.trim();
});
copyGreetingButton.addEventListener("click", copyGreeting);
saveJobButton.addEventListener("click", () => saveCurrentJob());
saveAndAnalyzeButton.addEventListener("click", () => saveCurrentJob({ analyze: true }));
readJobButton.addEventListener("click", () => readCurrentJob());
readCurrentJob({ automatic: true });
detectServiceStatus();

serviceControlButton.addEventListener("click", async (event) => {
  event.preventDefault();
  event.stopPropagation();
  if (serviceControlInProgress) return;
  serviceControlInProgress = true;
  serviceControlButton.disabled = true;
  try {
    if (localServiceState === "running") {
      console.debug("[service-control] manual stop clicked");
      await stopLocalService();
    } else {
      console.debug("[service-control] manual start clicked");
      showStatus("正在启动本地服务……", "loading");
      if (await startLocalService()) showStatus("本地服务已启动", "success");
    }
  } finally {
    serviceControlInProgress = false;
  }
});

analyzeJobButton.addEventListener("click", async () => {
  if (analysisInProgress || serviceControlInProgress) return;

  const jobTitle = pageTitle.textContent.trim();
  const description = jobDescription.value.trim();
  const candidateProfileText = candidateProfile.value.trim();
  if (!jobTitle || jobTitle === "尚未读取") {
    showStatus("岗位标题为空，请先读取当前岗位", "warning");
    return;
  }
  if (!description) {
    showStatus("岗位内容为空，请先读取或填写 JD", "warning");
    return;
  }
  if (!candidateProfileText) {
    showStatus("请先填写真实的个人技能或简历简介", "warning");
    return;
  }
  let authHeaders;
  try {
    authHeaders = demoAuthorizationHeaders();
  } catch {
    showStatus("请先填写有效的本地 Demo Token", "warning");
    return;
  }

  setLoadingState(true);
  analysisResult.hidden = true;
  greetingSection.hidden = true;

  try {
    if (!(await checkBackendHealth())) {
      if (nativeHostInstalled === null) await detectServiceStatus();
      if (localServiceState === "uninstalled") {
        showStatus(NATIVE_INSTALL_MESSAGE, "error");
        return;
      }
      if (!(await ensureServiceForAnalysis())) return;
    }

    analyzeLabel.textContent = "正在分析岗位……";
    showStatus("正在分析岗位……", "loading");
    const response = await fetch("http://127.0.0.1:8000/api/analyze-job", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({
        job_title: jobTitle,
        job_description: description,
        candidate_profile: candidateProfileText,
      }),
    });
    if (!response.ok) throw new Error(`Unexpected HTTP status: ${response.status}`);

    const analysis = await response.json();
    renderAnalysis(analysis);
    showStatus("AI 岗位分析完成", "success");
    if (typeof analysisResult.scrollIntoView === "function") {
      analysisResult.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (error) {
    console.error("AI job analysis failed:", error);
    const isConnectionError = error instanceof TypeError;
    showStatus(
      isConnectionError
        ? "后端未连接，请先启动本地服务"
        : "AI 分析失败，请稍后重试",
      "error",
    );
  } finally {
    setLoadingState(false);
  }
});

healthCheckButton.addEventListener("click", async () => {
  healthCheckButton.disabled = true;
  setBackendStatus("正在检查", "idle");
  showStatus("正在检查后端连接……", "loading");

  try {
    const state = await detectServiceStatus();
    if (state === "running") {
      showStatus("后端连接正常", "success");
    } else if (state === "uninstalled") {
      showStatus(NATIVE_INSTALL_MESSAGE, "error");
    } else {
      showStatus("后端未运行，可点击“启动本地服务”", "warning");
    }
  } catch (error) {
    console.error("Backend health check failed:", error);
    setServiceState("error");
    showStatus("本地服务状态检查失败", "error");
  } finally {
    healthCheckButton.disabled = false;
  }
});
