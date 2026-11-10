# Phase 8.2 Demo 演示脚本

## 演示目标

用 3 分钟展示一个可复现的完整闭环：Docker 一键启动 → 岗位工作台 → RAG 简历证据 → Agent Workflow → 可解释分析。扩展采集 JD 作为可选加演，不占主演示时间。

## 演示前准备

1. 确认 Docker Desktop 已启动，VPN/代理能够访问 Docker Hub。
2. 不打开 `.env`、请求头或 Docker 环境变量页面。
3. 双击 `start_demo.bat`，等待控制台显示 `Demo is ready`。
4. 浏览器保持 1440×900 左右，缩放 100%，关闭私人标签页、书签栏和通知。
5. 确认 Dashboard、Jobs、Resume 和一个 Job Detail 页面均可打开。
6. 若要现场触发 LLM / Embedding，提前在未提交的 `.env.docker` 中准备有效配置；否则只演示已保存的 Demo 分析。

## 3 分钟主演示

| 时间 | 页面与操作 | 讲解 |
| --- | --- | --- |
| 0:00–0:20 | 展示 `start_demo.bat` 完成与三个 healthy 服务 | “项目通过 Docker Compose 启动 Next.js、FastAPI 和 PostgreSQL/pgvector；migration 与空库 Seed 由明确的 Demo 初始化入口执行。” |
| 0:20–0:50 | Dashboard | “工作台汇总岗位、已分析数量、平均匹配度和待处理项，数据来自真实 Backend API。” |
| 0:50–1:15 | Jobs 列表并打开岗位 | “岗位、候选人画像和分析结果都持久化在 PostgreSQL，而不是写死在页面里。” |
| 1:15–2:05 | Job Detail：评分、分析、Agent 步骤 | “LLM 提取要求与证据，RAG 从简历知识库检索片段，受控 Agent 按固定节点执行，最终分数由后端确定性规则计算。” |
| 2:05–2:35 | Resume：文档与语义检索 | “PDF/DOCX 被解析、分块并写入 pgvector；检索结果可以回溯到真实简历片段。” |
| 2:35–3:00 | 架构图 | “浏览器经 Next.js 和 FastAPI 进入数据库、RAG 与 Agent；API Key 只存在于 Backend 运行环境。” |

## 可选 1 分钟扩展加演

1. 打开一个公开招聘详情页。
2. 按 `Alt+J` 打开 Manifest V3 扩展。
3. 展示选中文字优先与通用岗位区域提取。
4. 说明扩展只负责采集与交互，核心 RAG / Agent / 评分仍在 Backend。

不要现场展示真实 API Key，不要声称扩展适配所有招聘网站。

## 演示结束

双击：

```text
stop_demo.bat
```

说明容器和 network 会删除，但项目目录 `data/postgres` 中的数据库文件保留，因此下次启动仍有 Demo 数据。

## 失败兜底

| 故障 | 处理与话术 |
| --- | --- |
| Docker Hub 拉取失败 | 切换可访问 Registry 的代理节点；“这是镜像分发网络问题，不影响已完成的应用构建验收。” |
| Frontend 500 | 检查 Alembic current/head；“Frontend SSR 依赖业务 API，schema 落后会被完整暴露，而不是展示伪数据。” |
| LLM / Embedding 不可用 | 展示已保存分析；“外部 provider 失败不影响岗位、简历、Agent 状态和确定性评分的本地持久化。” |
| 浏览器扩展无法注入 | 换普通公开页面或手动选中 JD；“浏览器内置页和受限页面禁止脚本注入。” |

## 对外口径

可以说：

> AI Job Copilot 2.0 已完成本地 Docker 全栈 Demo，具备岗位管理、简历知识库、pgvector 检索、受控 Agent Workflow、确定性评分和浏览器 JD 采集能力。

不要说：

- 已达到公网生产可用或大规模用户验证标准。
- 匹配分数等于录用概率。
- 支持自动投递、自动聊天或所有招聘网站。
- LLM 输出完全准确或无需用户核验。
