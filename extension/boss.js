// Structured job extraction for BOSS 直聘 web pages (www.zhipin.com).
//
// extractBossJob is self-contained so the popup can inject it with
// chrome.scripting.executeScript. It only reads the page the user has opened:
// it never clicks, navigates, or sends requests to the site.
function extractBossJob(doc = document, href = window.location.href) {
  // The site swaps some characters for look-alike Kangxi radicals; fold them back.
  const foldRadicals = (value) =>
    value.replace(/[⺀-⿟]/g, (character) => character.normalize("NFKC"));
  const text = (element) =>
    foldRadicals(element?.innerText ?? "")
      .replace(/\r\n?/g, "\n")
      .replace(/[ \t ]+/g, " ")
      .replace(/ ?\n ?/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  const line = (element) => text(element).replace(/\s+/g, " ");
  // Salary digits are drawn with a private-use font (U+E031..U+E03A stand for 0..9).
  const salaryText = (element) =>
    line(element)
      .replace(/[-]/g, (character) => String(character.charCodeAt(0) - 0xe031))
      .replace(/[-]/g, "")
      .trim();
  const jobUrl = (value) => {
    const match = /\/job_detail\/([\w~-]+)\.html/.exec(value ?? "");
    return match ? `https://www.zhipin.com/job_detail/${match[1]}.html` : null;
  };
  const firstPart = (value) => value.split("·")[0].trim();
  const optional = (value) => value || null;

  let fields;
  const panel = doc.querySelector(".job-detail-box");
  const banner = doc.querySelector(".job-banner");
  if (panel) {
    // Search/list page: the selected job is rendered in a side panel.
    const tags = [...panel.querySelectorAll(".job-detail-header .tag-list li")].map(line);
    const activeCard = doc.querySelector(".job-card-wrap.active");
    const description = panel.querySelector(".job-detail-body .desc");
    fields = {
      title: line(panel.querySelector(".job-detail-info .job-name")),
      salary: salaryText(panel.querySelector(".job-detail-info .job-salary")),
      company:
        line(activeCard?.querySelector(".boss-name")) ||
        firstPart(line(panel.querySelector(".boss-info-attr"))),
      location:
        line(panel.querySelector(".job-address-desc")) ||
        line(activeCard?.querySelector(".company-location")) ||
        (tags[0] ?? ""),
      experience: tags[1] ?? "",
      education: tags[2] ?? "",
      description: text(description),
      truncated: Boolean(panel.querySelector(".job-detail-body .zp-more-info-layer-wrapper")),
      source_url:
        jobUrl(panel.querySelector(".more-job-btn")?.getAttribute("href")) ||
        jobUrl(activeCard?.querySelector("a.job-name")?.getAttribute("href")),
    };
  } else if (banner) {
    // Standalone job detail page.
    const description = doc.querySelector(".job-detail .job-sec-text:not(.fold-text)");
    const titleCompany = /_(.+?)招聘-BOSS直聘/.exec(doc.title ?? "");
    fields = {
      title: line(banner.querySelector(".name h1")),
      salary: salaryText(banner.querySelector(".name .salary")),
      company:
        firstPart(line(doc.querySelector(".job-boss-info .boss-info-attr"))) ||
        (titleCompany ? titleCompany[1].trim() : ""),
      location:
        line(doc.querySelector(".location-address")) ||
        line(banner.querySelector(".text-city")),
      experience: line(banner.querySelector(".text-experiece")),
      education: line(banner.querySelector(".text-degree")),
      description: text(description),
      truncated: Boolean(description?.querySelector(".zp-more-info-layer-wrapper")),
      source_url: jobUrl(href),
    };
  } else {
    return null;
  }

  if (!fields.title || !fields.source_url || fields.description.length < 30) {
    return null;
  }
  return {
    title: fields.title.slice(0, 500),
    company: optional(fields.company.slice(0, 300)),
    salary: optional(fields.salary.slice(0, 100)),
    location: optional(fields.location.slice(0, 200)),
    experience: optional(fields.experience.slice(0, 100)),
    education: optional(fields.education.slice(0, 100)),
    description: fields.description.slice(0, 8000),
    source_url: fields.source_url,
    // True when the site only shows part of the JD (visitor is not signed in).
    truncated: fields.truncated,
  };
}

// Content-script part: runs only on www.zhipin.com (see manifest.json) and only
// reports jobs after the user turned on auto capture in the popup.
if (
  typeof chrome !== "undefined" &&
  chrome.runtime?.id &&
  typeof MutationObserver !== "undefined" &&
  typeof location !== "undefined" &&
  location.hostname === "www.zhipin.com"
) {
  let lastReportedUrl = null;
  let timer = null;

  const report = async () => {
    const { bossAutoCapture } = await chrome.storage.local.get({ bossAutoCapture: false });
    if (!bossAutoCapture) return;
    const job = extractBossJob();
    if (!job || job.truncated || job.source_url === lastReportedUrl) return;
    lastReportedUrl = job.source_url;
    chrome.runtime.sendMessage({ type: "boss-job-captured", job }).catch(() => {
      lastReportedUrl = null;
    });
  };

  const schedule = () => {
    clearTimeout(timer);
    // Wait for the detail panel to settle after the user opens another job.
    timer = setTimeout(() => report().catch(() => {}), 1200);
  };

  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
  schedule();
}
