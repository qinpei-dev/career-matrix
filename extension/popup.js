const healthCheckButton = document.querySelector("#health-check");
const readJobButton = document.querySelector("#read-job");
const analyzeJobButton = document.querySelector("#analyze-job");
const saveJobButton = document.querySelector("#save-job");
const saveAndAnalyzeButton = document.querySelector("#save-and-analyze");
const demoToken = document.querySelector("#demo-token");
const demoTokenHelp = document.querySelector("#demo-token-help");
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
const autoCapture = document.querySelector("#auto-capture");
const autoAnalyze = document.querySelector("#auto-analyze");
const autoCaptureStatus = document.querySelector("#auto-capture-status");
const greetingMode = document.querySelector("#greeting-mode");
const greetingTemplate = document.querySelector("#greeting-template");
const greetingCustom = document.querySelector("#greeting-custom");
const greetingTemplateBox = document.querySelector("#greeting-template-box");
const greetingCustomBox = document.querySelector("#greeting-custom-box");
const oneClickGreetButton = document.querySelector("#one-click-greet");
const profileSource = document.querySelector("#profile-source");
// Structured fields (company, salary, ...) when the page is a supported job site.
let currentListing = null;
// True when the active tab is on the job site, where one-click greeting works.
let onListingSite = false;
let generatedGreeting = "";
let jobDescriptionEdited = false;
let analysisInProgress = false;
let saveInProgress = false;
let serviceControlInProgress = false;
let copyFeedbackTimer;
let localServiceState = "unknown";
let nativeHostInstalled = null;
let lastReadUrl = null;
let followTimer;
let readInProgress = false;
// What the page looked like at the last read, and a change seen once but not
// yet confirmed (the page may still be rendering).
let lastPageFingerprint = null;
let pendingPageFingerprint = null;
const PAGE_POLL_INTERVAL = 1500;

const HEALTH_URL = "http://127.0.0.1:8000/health";
const NATIVE_INSTALL_MESSAGE =
  "首次使用需要安装本地连接组件，请运行项目目录中的 install_native_host.bat。";

const CANDIDATE_PROFILE_STORAGE_KEY = "aiJobCopilot.candidateProfile";
const DEFAULT_CANDIDATE_PROFILE =
  "大数据专业学生，掌握 Python、FastAPI、Git，使用过 Linux，完成过 AI Agent 项目。" +
  "了解 SQL，Docker 处于基础学习阶段，暂无正式开发实习经历。";

const LISTING_URL_PATTERN = /^https:\/\/www\.zhipin\.com\//;
const DEFAULT_GREETING_TEMPLATE =
  "您好，我对贵司的{岗位}岗位很感兴趣，我的技能和项目经历与岗位要求比较匹配，方便的话希望能进一步沟通，谢谢！";
// chrome.storage is shared with the background worker and the capture script.
const extensionStorage = typeof chrome !== "undefined" ? chrome.storage?.local : undefined;

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
  const payload = {
    title,
    company: null,
    description,
    source_url: pageUrl.textContent.trim() || null,
    source_type: "extension",
  };
  if (currentListing) {
    Object.assign(payload, {
      company: currentListing.company,
      salary: currentListing.salary,
      location: currentListing.location,
      experience: currentListing.experience,
      education: currentListing.education,
      source_type: "zhipin",
    });
  }
  return payload;
}

function showGreeting() {
  greetingTemplateBox.hidden = greetingMode.value !== "fixed";
  greetingCustomBox.hidden = greetingMode.value !== "custom";
  let text = generatedGreeting;
  if (greetingMode.value === "custom") {
    text = greetingCustom.value.trim();
  } else if (greetingMode.value === "fixed") {
    text = greetingTemplate.value
      .replaceAll("{岗位}", currentListing?.title || pageTitle.textContent.trim())
      .replaceAll("{公司}", currentListing?.company || "贵公司")
      .trim();
  }
  greetingTextarea.value = text;
  greetingSection.hidden = !text;
  copyGreetingButton.disabled = !text;
  oneClickGreetButton.disabled = !text || !onListingSite;
}

function showAutoCaptureStatus(count) {
  autoCaptureStatus.className = "field-help";
  autoCaptureStatus.textContent = autoCapture.checked
    ? `自动采集已开启，已保存 ${count} 个岗位`
    : "自动采集未开启";
}

// Ask the background worker to read the token from the project's .env.
async function loadDemoTokenFromProject() {
  const response = await new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "load-demo-token" }, (reply) => {
      resolve(chrome.runtime.lastError ? null : reply);
    });
  });
  if (!response?.ok) {
    demoTokenHelp.textContent = `未能自动读取 Token：${response?.error || "后台无响应"}。可手动填写。`;
    demoTokenHelp.className = "field-help status-warning";
    return "";
  }
  const { demoToken: token } = await extensionStorage.get({ demoToken: "" });
  demoTokenHelp.textContent = "已自动从项目 .env 读取 Token。";
  demoTokenHelp.className = "field-help";
  return token;
}

async function loadExtensionSettings() {
  greetingTemplate.value = DEFAULT_GREETING_TEMPLATE;
  if (!extensionStorage) return;
  const settings = await extensionStorage.get({
    bossAutoCapture: false,
    bossAutoAnalyze: true,
    bossCapturedCount: 0,
    demoToken: "",
    greetingMode: "generated",
    greetingTemplate: DEFAULT_GREETING_TEMPLATE,
    customGreeting: "",
  });
  autoCapture.checked = settings.bossAutoCapture;
  autoAnalyze.checked = settings.bossAutoAnalyze;
  if (!settings.demoToken) settings.demoToken = await loadDemoTokenFromProject();
  if (settings.demoToken && !demoToken.value) demoToken.value = settings.demoToken;
  greetingMode.value = settings.greetingMode;
  greetingTemplate.value = settings.greetingTemplate;
  greetingCustom.value = settings.customGreeting;
  showAutoCaptureStatus(settings.bossCapturedCount);
  showGreeting();
}

async function saveAutoCaptureSettings() {
  if (!extensionStorage) return;
  if (!autoCapture.checked) {
    await extensionStorage.set({ bossAutoCapture: false, bossAutoAnalyze: autoAnalyze.checked });
    chrome.action?.setBadgeText({ text: "" });
    showAutoCaptureStatus(0);
    return;
  }
  if (!demoToken.value.trim()) demoToken.value = await loadDemoTokenFromProject();
  try {
    demoAuthorizationHeaders();
  } catch {
    autoCapture.checked = false;
    // Explain right under the checkbox and jump to the token field; the shared
    // status line sits far below and is easy to miss.
    autoCaptureStatus.textContent = "勾选失败：请先在下方“本地 Demo Token”填写 Token，再勾选";
    autoCaptureStatus.className = "field-help status-warning";
    demoToken.scrollIntoView?.({ behavior: "smooth", block: "center" });
    demoToken.focus?.();
    showStatus("请先填写有效的本地 Demo Token，再开启自动采集", "warning");
    return;
  }
  await extensionStorage.set({
    bossAutoCapture: true,
    bossAutoAnalyze: autoAnalyze.checked,
    demoToken: demoToken.value.trim(),
  });
  const { bossCapturedCount } = await extensionStorage.get({ bossCapturedCount: 0 });
  showAutoCaptureStatus(bossCapturedCount);
  showStatus("自动采集已开启，刷新招聘网站页面后生效", "success");
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

  generatedGreeting = safeText(analysis.greeting).trim();
  showGreeting();
  analysisResult.hidden = false;
}

function setReadSource(source, successful) {
  const labels = {
    selection: "当前选中文本",
    "smart-job-detail": "智能岗位详情识别",
    listing: "招聘网站岗位详情（含薪资、地点）",
    main: "页面主要内容",
    article: "页面主要内容",
    "role-main": "页面主要内容",
    body: "整页正文回退",
  };
  readSource.textContent = labels[source] || (successful ? "页面内容" : "读取失败");
}

// Digits and spacing are left out so ticking timers or counters on the page
// do not look like a new job.
function pageFingerprint(page) {
  return page ? `${page.url}|${page.title}|${String(page.text).replace(/[\d\s]/g, "")}` : null;
}

async function readCurrentJob({ automatic = false } = {}) {
  readInProgress = true;
  readJobButton.disabled = true;
  showStatus("正在读取当前网页……", "loading");

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error("No active tab is available");

    const injectionResults = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractJobContent,
    });
    let page = injectionResults[0]?.result;
    if (!page) throw new Error("The page did not return readable content");
    lastPageFingerprint = pageFingerprint(page);

    currentListing = null;
    onListingSite = LISTING_URL_PATTERN.test(page.url || "");
    if (onListingSite && page.source !== "selection") {
      const listingResults = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: extractBossJob,
      });
      const listing = listingResults[0]?.result;
      if (listing && !listing.truncated) {
        currentListing = listing;
        page = {
          ...page,
          title: listing.title,
          url: listing.source_url,
          text: listing.description,
          source: "listing",
        };
      }
    }

    console.debug("Job content extraction", {
      source: page.source,
      candidateCount: page.debug?.candidateCount ?? 0,
      score: page.debug?.score ?? null,
      textLength: page.debug?.textLength ?? page.text.length,
    });
    if (page.url !== lastReadUrl) {
      // Another job: drop the previous job's edits and analysis.
      if (lastReadUrl !== null) {
        jobDescriptionEdited = false;
        generatedGreeting = "";
        analysisResult.hidden = true;
      }
      lastReadUrl = page.url;
    }
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
    } else if (page.source === "listing") {
      showStatus("已读取岗位详情及薪资、地点等信息", "success");
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
    showStatus(
      automatic
        ? "当前页面无法自动读取，可点击工具栏图标后再点“读取当前岗位”"
        : "无法读取当前网页，请确认页面允许扩展访问后重试",
      "error",
    );
  } finally {
    readInProgress = false;
    readJobButton.disabled = false;
    showGreeting();
  }
}

function formatProfile(profile) {
  return [
    profile.target_role && `目标岗位：${profile.target_role}`,
    profile.summary,
    asArray(profile.skills).length && `技能：${asArray(profile.skills).join("、")}`,
  ]
    .filter(Boolean)
    .join("\n");
}

// Use the candidate profile kept in the web workspace (built from the uploaded
// resume) instead of the hand-written default text.
async function syncCandidateProfile() {
  let headers;
  try {
    headers = demoAuthorizationHeaders();
  } catch {
    return;
  }
  try {
    const response = await fetch("http://127.0.0.1:8000/api/v1/profiles/me", { headers });
    if (response.status === 404) {
      profileSource.textContent = "Web 工作台里还没有候选人资料，可在工作台上传简历生成；暂用下方文字。";
      return;
    }
    if (!response.ok) return;
    const text = formatProfile(await response.json());
    if (!text) return;
    candidateProfile.value = text;
    profileSource.textContent = "已同步 Web 工作台里的候选人资料（来自你上传的简历）；在这里改动只影响本次分析。";
  } catch {
    // Backend not running yet; keep the local text.
  }
}

// Open the chat for the job on screen and put the greeting in the chat box.
// The user reviews it and presses send; nothing is sent from here.
async function oneClickGreet() {
  const text = greetingTextarea.value.trim();
  if (!text || !extensionStorage) return;
  oneClickGreetButton.disabled = true;
  try {
    await navigator.clipboard.writeText(text).catch(() => {});
    await extensionStorage.set({ pendingGreeting: { text, createdAt: Date.now() } });
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const [{ result } = {}] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: openBossChat,
    });
    if (!result?.ok) {
      await extensionStorage.remove("pendingGreeting");
      showStatus("没找到“立即沟通”按钮，文案已复制，请手动打开聊天后按 Ctrl+V", "warning");
      return;
    }
    if (result.clicked === "立即沟通") {
      await wait(1500);
      await chrome.scripting
        .executeScript({ target: { tabId: tab.id }, func: clickContinueChat })
        .catch(() => {});
    }
    showStatus("正在打开聊天并填入文案，请检查后自己按发送（文案也已复制，可 Ctrl+V）", "success");
  } catch (error) {
    console.error("One-click greeting failed:", error);
    showStatus("一键打招呼失败，文案已复制，可手动打开聊天后按 Ctrl+V", "error");
  } finally {
    showGreeting();
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
oneClickGreetButton.addEventListener("click", oneClickGreet);
greetingCustom.addEventListener("input", () => {
  extensionStorage?.set({ customGreeting: greetingCustom.value });
  showGreeting();
});
autoCapture.addEventListener("change", saveAutoCaptureSettings);
// Remember the token in this browser's extension storage so it is typed once.
demoToken.addEventListener("change", () => {
  const token = demoToken.value.trim();
  if (token) extensionStorage?.set({ demoToken: token });
  else extensionStorage?.remove("demoToken");
});
autoAnalyze.addEventListener("change", saveAutoCaptureSettings);
greetingMode.addEventListener("change", () => {
  extensionStorage?.set({ greetingMode: greetingMode.value });
  showGreeting();
});
greetingTemplate.addEventListener("input", () => {
  extensionStorage?.set({ greetingTemplate: greetingTemplate.value });
  showGreeting();
});
loadExtensionSettings().then(syncCandidateProfile);
saveJobButton.addEventListener("click", () => saveCurrentJob());
saveAndAnalyzeButton.addEventListener("click", () => saveCurrentJob({ analyze: true }));
readJobButton.addEventListener("click", () => readCurrentJob());
readCurrentJob({ automatic: true });
detectServiceStatus();
followActiveTab();

// The floating window stays open while the user browses: re-read the page
// whenever it finishes loading or the user opens another job on a job site.
function followActiveTab() {
  if (!chrome.tabs?.onUpdated) return;
  const refresh = () => {
    clearTimeout(followTimer);
    followTimer = setTimeout(() => {
      // Each tab has its own floating window; only the visible one re-reads.
      if (analysisInProgress || saveInProgress || document.visibilityState === "hidden") return;
      readCurrentJob({ automatic: true });
    }, 300);
  };
  chrome.tabs.onUpdated.addListener((_tabId, changeInfo, tab) => {
    if (tab.active && changeInfo.status === "complete") refresh();
  });
  chrome.runtime.onMessage?.addListener((message, sender) => {
    if (message?.type === "listing-changed" && sender.tab?.active) refresh();
  });
  // Job sites change the selected job without loading a new page and their
  // markup changes over time, so also watch the page content itself: when the
  // job text on screen changes and stays changed, read it again.
  setInterval(() => pollPageChange().catch(() => {}), PAGE_POLL_INTERVAL);
}

async function pollPageChange() {
  if (
    readInProgress ||
    analysisInProgress ||
    saveInProgress ||
    lastPageFingerprint === null ||
    document.visibilityState === "hidden"
  ) {
    return;
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;
  const [{ result: page } = {}] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: extractJobContent,
  });
  // Selecting text to copy it must not replace the JD.
  if (!page || page.source === "selection") return;
  const fingerprint = pageFingerprint(page);
  if (fingerprint === lastPageFingerprint) {
    pendingPageFingerprint = null;
    return;
  }
  if (fingerprint !== pendingPageFingerprint) {
    pendingPageFingerprint = fingerprint;
    return;
  }
  pendingPageFingerprint = null;
  await readCurrentJob({ automatic: true });
}

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
