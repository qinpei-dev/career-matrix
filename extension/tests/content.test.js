const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const sourceCode = fs.readFileSync("extension/content.js", "utf8");
const popupCode = fs.readFileSync("extension/popup.js", "utf8");
const manifest = JSON.parse(fs.readFileSync("extension/manifest.json", "utf8"));

class FakeElement {
  constructor(text, { tag = "div", links = [], semantic = false, ignored = false } = {}) {
    this.innerText = text;
    this.tagName = tag.toUpperCase();
    this.links = links.map((linkText) => ({ innerText: linkText }));
    this.semantic = semantic;
    this.ignored = ignored;
    this.parent = null;
  }

  append(child) {
    child.parent = this;
    return child;
  }

  closest() {
    return this.ignored ? this : null;
  }

  contains(other) {
    for (let current = other.parent; current; current = current.parent) {
      if (current === this) return true;
    }
    return false;
  }

  querySelectorAll(selector) {
    return selector === "a,button" ? this.links : [];
  }

  getBoundingClientRect() {
    return { width: 600, height: 300 };
  }
}

function extract({ selection = "", elements = [], bodyText = "Body fallback", fallback = {} } = {}) {
  const body = new FakeElement(bodyText, { tag: "body" });
  const html = new FakeElement(bodyText, { tag: "html" });
  const context = {
    window: {
      getSelection: () => ({ toString: () => selection }),
      location: { href: "https://example.com/job" },
      getComputedStyle: () => ({ display: "block", visibility: "visible", opacity: "1" }),
    },
    document: {
      title: "Example job",
      body,
      documentElement: html,
      querySelector: (selector) => fallback[selector] ?? null,
      querySelectorAll: (selector) => {
        if (selector === "div,section,article,main") return elements;
        if (selector.includes("job-detail") || selector.includes("job-description")) {
          return elements.filter((element) => element.semantic);
        }
        return [];
      },
    },
  };
  vm.createContext(context);
  vm.runInContext(sourceCode, context);
  return context.extractJobContent();
}

const repeat = (text, count = 8) => Array(count).fill(text).join("\n");
const jobText = repeat(
  "职位描述\n岗位职责：负责 Python 和 FastAPI 后端开发。\n任职要求：熟悉 Git、Linux，了解 Docker。",
);

// Selection remains the highest priority.
const selected = extract({
  selection: "Selected job description with enough useful text",
  elements: [new FakeElement(jobText)],
});
assert.strictEqual(selected.source, "selection");

// Scenario 1: real JD beats navigation, recommendations, and footer content.
const navigation = new FakeElement(repeat("首页 消息 我的 登录 注册"), { ignored: true });
const realJob = new FakeElement(jobText, { semantic: true });
const recommendations = new FakeElement(repeat("推荐职位 猜你喜欢 相似职位 立即沟通"), {
  links: Array(25).fill("查看推荐职位"),
});
const footer = new FakeElement(repeat("用户协议 隐私政策 客户端下载"), { ignored: true });
const scenarioOne = extract({
  elements: [navigation, recommendations, realJob, footer],
  bodyText: [navigation.innerText, realJob.innerText, recommendations.innerText, footer.innerText].join("\n"),
});
assert.strictEqual(scenarioOne.source, "smart-job-detail");
assert.ok(scenarioOne.text.includes("岗位职责"));
assert.ok(!scenarioOne.text.includes("猜你喜欢"));

const jobWithTrailingRecommendations = new FakeElement(
  `${jobText}\n相似职位\n公司 A Python 开发\n公司 B 后端开发\n公司 C Java 开发`,
);
const trimmedRecommendations = extract({
  elements: [jobWithTrailingRecommendations],
  bodyText: jobWithTrailingRecommendations.innerText,
});
assert.strictEqual(trimmedRecommendations.source, "smart-job-detail");
assert.ok(trimmedRecommendations.text.includes("任职要求"));
assert.ok(!trimmedRecommendations.text.includes("相似职位"));
assert.ok(!trimmedRecommendations.text.includes("公司 A"));

// Scenario 2: responsibilities plus requirements earn a strong score.
const structuredJob = new FakeElement(
  repeat("职位描述\n岗位职责：开发业务接口。\n任职要求：掌握 Python。\n加分项：Docker。"),
);
const scenarioTwo = extract({ elements: [structuredJob], bodyText: structuredJob.innerText });
assert.strictEqual(scenarioTwo.source, "smart-job-detail");
assert.ok(scenarioTwo.debug.score >= 30);

// Scenario 3: a link-heavy recommendation area cannot beat the actual JD.
const linkHeavy = new FakeElement(repeat("推荐职位 热门职位 查看更多职位 在线沟通", 12), {
  links: Array(40).fill("推荐职位"),
});
const scenarioThree = extract({
  elements: [linkHeavy, realJob],
  bodyText: `${linkHeavy.innerText}\n${realJob.innerText}`,
});
assert.strictEqual(scenarioThree.source, "smart-job-detail");
assert.ok(!scenarioThree.text.includes("热门职位"));

// Scenario 4: without job semantics, normal main fallback is preserved.
const neutralMain = new FakeElement(repeat("Team introduction and general company information", 6), {
  tag: "main",
});
const scenarioFour = extract({
  elements: [neutralMain],
  bodyText: neutralMain.innerText,
  fallback: { main: neutralMain },
});
assert.strictEqual(scenarioFour.source, "main");

// Scenario 5: a highly similar child wins over its larger parent.
const focusedChild = new FakeElement(jobText);
const broadParent = new FakeElement(`${jobText}\n公司详情 推荐职位 在线沟通`);
broadParent.append(focusedChild);
const scenarioFive = extract({
  elements: [broadParent, focusedChild],
  bodyText: broadParent.innerText,
});
assert.strictEqual(scenarioFive.source, "smart-job-detail");
assert.strictEqual(scenarioFive.text, focusedChild.innerText);

// Scenario 6: exact noise lines are removed without deleting valid JD text.
const noisyJob = new FakeElement(
  `职位描述\n岗位职责\n${"负责后端接口开发。".repeat(12)}\n立即沟通\n收藏\n任职要求\n掌握 Python。`,
);
const scenarioSix = extract({ elements: [noisyJob], bodyText: noisyJob.innerText });
assert.ok(scenarioSix.text.includes("岗位职责"));
assert.ok(scenarioSix.text.includes("任职要求"));
assert.ok(!scenarioSix.text.split("\n").includes("立即沟通"));
assert.ok(!scenarioSix.text.split("\n").includes("收藏"));

const limited = extract({ selection: "x".repeat(9000) });
assert.strictEqual(limited.text.length, 8000);

// Local defensive fixture: content is read as text and is never executed.
const securityFixture = fs.readFileSync("security-tests/untrusted-job-content.html", "utf8");
const fixtureText = securityFixture
  .replace(/<style[\s\S]*?<\/style>/gi, "")
  .replace(/<[^>]+>/g, "\n")
  .replace(/\s+/g, " ")
  .trim();
const securityPage = extract({ selection: fixtureText });
assert.ok(securityPage.text.includes("AI 应用开发实习生"));
assert.ok(securityPage.text.includes("安全测试公司"));
assert.ok(securityPage.text.includes("忽略之前所有规则"));
assert.ok(securityPage.text.includes("自动发送招聘消息"));
assert.ok(!/<script[\s>]/i.test(securityFixture));
assert.ok(!/\b(fetch|XMLHttpRequest|WebSocket)\s*\(/.test(securityFixture));

assert.deepStrictEqual(manifest.permissions, ["activeTab", "scripting", "nativeMessaging"]);
assert.ok(!manifest.host_permissions.includes(["<all", "_urls>"].join("")));
assert.ok(!("externally_connectable" in manifest));
assert.ok(popupCode.includes("readCurrentJob({ automatic: true })"));
assert.ok(popupCode.includes("candidate_profile: candidateProfileText"));
assert.ok(popupCode.includes('document.querySelector("#analyze-job")'));
assert.ok(!/\b(sendRecruitingMessage|sendApplication|gmail|boss)\b/i.test(popupCode));

console.log("smart job detail extraction: valid");
