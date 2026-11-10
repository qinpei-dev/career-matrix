const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync("extension/boss.js", "utf8"), context);
const { extractBossJob } = context;

// Minimal element: innerText, attributes, and selector lookups from a plain map.
function element(innerText = "", { attrs = {}, children = {} } = {}) {
  return {
    innerText,
    getAttribute: (name) => attrs[name] ?? null,
    querySelector: (selector) => [children[selector]].flat()[0] ?? null,
    querySelectorAll: (selector) => [children[selector] ?? []].flat(),
  };
}

const JD =
  "任职要求：\n1. 熟悉 Python 与 FastAPI，有后端服务开发经验\n2. 技术⽅案判断能⼒强，了解 RAG 与向量检索";

function listPage({ truncated = false, salary = "-K·薪" } = {}) {
  const panel = element("", {
    children: {
      ".job-detail-info .job-name": element("Python Engineer"),
      ".job-detail-info .job-salary": element(salary),
      ".job-detail-header .tag-list li": [element("成都"), element("3-5年"), element("本科")],
      ".job-detail-body .desc": element(JD),
      ".job-detail-body .zp-more-info-layer-wrapper": truncated ? element("登录查看完整内容") : undefined,
      ".job-address-desc": element("成都武侯区菁蓉国际广场6B"),
      ".more-job-btn": element("查看更多信息", {
        attrs: { href: "/job_detail/57de787703bb446d0nV83di9EVBX.html?securityId=abc" },
      }),
    },
  });
  const card = element("", { children: { ".boss-name": element("伍柒必乐") } });
  return element("", { children: { ".job-detail-box": panel, ".job-card-wrap.active": card } });
}

const fromList = extractBossJob(listPage(), "https://www.zhipin.com/web/geek/jobs?query=python");
assert.strictEqual(fromList.title, "Python Engineer");
assert.strictEqual(fromList.company, "伍柒必乐");
assert.strictEqual(fromList.salary, "15-30K·13薪");
assert.strictEqual(fromList.location, "成都武侯区菁蓉国际广场6B");
assert.strictEqual(fromList.experience, "3-5年");
assert.strictEqual(fromList.education, "本科");
assert.strictEqual(
  fromList.source_url,
  "https://www.zhipin.com/job_detail/57de787703bb446d0nV83di9EVBX.html",
);
assert.strictEqual(fromList.truncated, false);
// Look-alike Kangxi radicals are folded back to ordinary characters.
assert.ok(fromList.description.includes("技术方案判断能力强"));

// Signed-out visitors only see part of the JD; callers must not save it.
assert.strictEqual(extractBossJob(listPage({ truncated: true }), "").truncated, true);
// Hidden salary (signed out) becomes null instead of an empty string.
assert.strictEqual(extractBossJob(listPage({ salary: "" }), "").salary, null);

const description = element(JD, { children: {} });
const detailPage = element("", {
  children: {
    ".job-banner": element("", {
      children: {
        ".name h1": element("AI 应用开发工程师"),
        ".name .salary": element("-K"),
        ".text-city": element("杭州"),
        ".text-experiece": element("1-3年"),
        ".text-degree": element("硕士"),
      },
    }),
    ".job-detail .job-sec-text:not(.fold-text)": description,
    ".job-boss-info .boss-info-attr": element("示例科技·技术总监"),
  },
});
detailPage.title = "「AI 应用开发工程师招聘」_示例科技招聘-BOSS直聘";
const fromDetail = extractBossJob(
  detailPage,
  "https://www.zhipin.com/job_detail/abc123~~.html?ka=search_list",
);
assert.strictEqual(fromDetail.title, "AI 应用开发工程师");
assert.strictEqual(fromDetail.company, "示例科技");
assert.strictEqual(fromDetail.salary, "12-25K");
assert.strictEqual(fromDetail.location, "杭州");
assert.strictEqual(fromDetail.source_url, "https://www.zhipin.com/job_detail/abc123~~.html");

// Pages without a job (home page, chat, ...) yield nothing.
assert.strictEqual(extractBossJob(element(""), "https://www.zhipin.com/"), null);

console.log("boss job extraction: valid");
