# 项目状态说明

## 当前结论

CareerMatrix 是 **AI-Powered Career Intelligence & Decision System**。它已具备本地 MVP 的核心闭环：Edge 优先、Chrome 兼容的 Manifest V3 扩展读取岗位内容和候选人资料，本地 FastAPI 提取岗位要求与候选人证据，再由后端按固定权重计算多维结构化匹配结果。系统覆盖 job discovery、application planning、RAG、受控 Agent workflow、application tracking 与 human-in-the-loop 决策支持；API Key 只保留在后端。仓库提供 Windows 一键启动/停止入口，并包含 pytest 和 Node 测试。项目没有云端部署，未进行大规模用户验证；评分仅供参考，不等于录用概率。当前也没有自动投递或自动聊天，不具备生产系统所需的账号、鉴权、云端存储和运维能力。

## Native service workflow（v1.2）

Windows + Microsoft Edge 的 Native Messaging 集成已完成真实本地验收。扩展版本为 `0.1.2`。
用户为真实扩展 ID 完成一次当前用户 HKCU 注册后，可直接在岗位页面按 `Alt+J` 并点击“分析岗位”；后端会按需启动、通过健康检查后继续一次分析，也可在 popup 中手动启动或停止。
Host 每次只处理一条 `status`、`start` 或 `stop` 白名单消息，且复用现有启停脚本的进程归属判断。
这项能力需要开发者加载解压缩扩展并手动运行一次安装脚本，不代表已经达到普通用户一键安装的产品水平，
不支持 macOS/Linux，也不是 Edge 商店正式安装包。

## 功能状态矩阵

| 能力 | 状态 | 代码或验证依据 |
| --- | --- | --- |
| Edge 优先、Chrome 兼容的 Manifest V3 扩展 | 已实现 | `extension/manifest.json` |
| `Alt+J` 打开扩展 | 已实现 | manifest `_execute_action` |
| popup 打开后自动读取岗位 | 已实现 | `readCurrentJob({ automatic: true })` |
| 选中文字优先 | 已实现 | `extractJobContent()` 的 selection 分支 |
| 智能岗位详情区域识别 | 已实现 | 候选元素评分与阈值选择 |
| `main/article/role-main/body` 回退 | 已实现 | `content.js` 回退链 |
| 部分按钮与推荐职位噪声清理 | 已实现 | `noiseLines` 与尾部推荐标题集合 |
| JD 手动修改与重新读取保护 | 已实现 | 可编辑 textarea、覆盖确认和编辑状态 |
| `candidate_profile` 输入 | 已实现 | popup 表单与三字段请求 |
| 候选人资料 localStorage 保存 | 已实现 | `aiJobCopilot.candidateProfile` |
| Windows 一键启动与停止 | 已实现 | `start_ai_job_copilot.bat`、`stop_ai_job_copilot.bat`、`scripts/*.ps1` |
| Edge 扩展内按需启停与分析自动续接 | 已实现并完成本地验收 | Native Messaging、`native_host/`、安装/卸载脚本 |
| FastAPI 根接口、健康检查和分析接口 | 已实现 | `backend/app/main.py` |
| DeepSeek 要求与证据提取 | 已实现 | `backend/app/services/llm.py` |
| 后端确定性评分 | 已实现 | `backend/app/services/scoring.py` 的固定状态映射与维度权重 |
| API Key 后端隔离 | 已实现（本地边界） | Key 从后端环境或 `.env` 读取，扩展不包含 Key |
| Pydantic 请求/响应校验 | 已实现 | `JobAnalysisRequest`、严格 `JobAnalysis` |
| 结构化岗位匹配结果 | 已实现 | `score_breakdown`、四类技能、证据、建议、理由和 greeting |
| 新版结果 UI | 已实现 | score 卡片、技能标签、评分依据折叠区、loading/错误状态、自动滚动 |
| greeting 编辑与复制 | 已实现 | textarea、复制按钮与成功/失败反馈 |
| 上游与格式异常处理 | 已实现 | `LLMServiceError` 体系和 API 转换 |
| pytest 与 Node 测试 | 已实现 | 功能分支回归 pytest 43 项、content 与 popup Node 测试通过 |
| 合并后真实 DeepSeek 联调 | 未运行 | 依赖个人 Key，按本次合并要求不调用真实 API |
| 线上部署 / 生产可用 | 未实现 | 当前为本地 MVP |
| 自动投递 / 自动聊天 / 自动刷新岗位 | 未实现 | 不在当前功能范围 |
| 全招聘网站稳定适配 | 未实现 | 当前为通用启发式 + 手动兜底 |
| 账号、云同步、团队协作 | 未实现 | 当前无相关模块 |

## 已验证的自动化场景

- FastAPI 根接口与健康检查。
- `candidate_profile` 必填、去除首尾空白并进入模型服务。
- 合法 JSON、被文本包围的 JSON、非法 JSON、旧模型自由 score 忽略和安全错误响应。
- 固定权重评分、技能四态分类、不适用维度权重归一化和 `score_breakdown`。
- popup 中候选人资料输入、localStorage、自动读取、新字段与旧响应兼容渲染、loading、自动滚动和复制反馈。
- 选中文字优先、岗位详情与推荐区域竞争、尾部推荐裁剪、语义回退、父子候选选择、噪声行过滤和 8,000 字符上限。

## 仍需人工验证的内容

- 具体招聘网站在当前页面版本下的提取效果。
- Edge 与 Chrome 实际加载、权限提示和快捷键冲突情况。
- 真实网络环境中的 DeepSeek 延迟、限流和输出质量。
- 候选人对匹配结果、建议和打招呼文案的人工核验。

## 对外说明口径

推荐说法：

> CareerMatrix 是一个 AI-Powered Career Intelligence & Decision System：它结合岗位发现、多维岗位/候选人匹配、RAG 证据检索、受控 Agent workflow、申请规划与人工确认，提供可解释的职业决策支持；扩展可按需启动本地后端并续接一次分析请求。

不推荐说法：

- “已上线并服务真实用户。”
- “适配所有招聘网站。”
- “匹配分数等于客观录用概率。”
- “AI 能准确判断是否会通过面试。”
- “候选人数据已经达到生产级安全合规。”
- “支持自动投递、自动聊天或绕过网站限制。”
