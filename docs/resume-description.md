# 简历项目描述

下面提供不同长度的真实表述，可按版面选用。不要同时堆叠所有版本。项目当前是本地 MVP，没有数据库或云端部署，未进行大规模用户验证；后端固定规则评分仅供求职辅助参考，不等于录用概率，也没有实现自动投递或自动聊天。

## 一句话版本

CareerMatrix｜AI-Powered Career Intelligence & Decision System，基于 Manifest V3、FastAPI 与 DeepSeek，实现招聘页 JD 提取、候选人证据提取、后端确定性评分和可解释结果展示。

## 标准版本

**CareerMatrix｜个人项目｜JavaScript / Manifest V3 / FastAPI / Pydantic / DeepSeek**

- 开发 Edge 优先、兼容 Chrome 的 Manifest V3 扩展，实现 popup 自动读取岗位、`Alt+J` 快捷唤起、选中文字优先及 `main/article/role-main/body` 多级回退。
- 设计通用岗位详情启发式提取，根据关键词、文本结构、交互占比与父子节点关系筛选正文，并清理部分按钮和尾部推荐职位噪声。
- 搭建 FastAPI 分析接口，将 `candidate_profile` 与 JD 分离传递给 DeepSeek；模型只提取岗位要求、技能状态和候选人证据，API Key 仅由后端环境读取。
- 实现固定权重评分模块，将 matched / partial / unverified / missing 映射为确定分值，输出总分与 `score_breakdown`，并忽略旧模型自由生成的 score。
- 完成 score 卡片、技能标签、评分依据、greeting 编辑/复制及完整异步状态；通过 Windows + Edge Native Messaging 按需启动后端，Host 仅允许 `status/start/stop`。
- 编写 pytest 与 Node 测试覆盖接口、评分、Native Host 协议与安全边界、扩展权限、岗位提取和 popup 防重复交互；发布回归 pytest 44 项及两个 Node 测试通过。

## 精简三点版本

- 使用 Manifest V3 开发 Edge/Chrome 扩展，实现招聘页 JD 自动提取、选中文字优先、智能正文识别和多级语义回退。
- 使用 FastAPI + DeepSeek 提取候选人证据与岗位要求，通过后端 Key 隔离和严格 Pydantic 校验稳定前后端契约。
- 后端按固定权重计算总分与评分依据；以 pytest 和 Node 覆盖接口、评分、异常、权限、localStorage、提取与 popup 交互场景。

## 面向不同岗位的侧重点

### 后端 / Python 岗

突出 FastAPI 请求模型、DeepSeek 证据提取、确定性评分模块、Pydantic 响应校验、安全错误映射和 pytest。不要把当前项目描述成微服务、分布式系统或生产级 API 平台。

### 前端 / 浏览器扩展岗

突出 Manifest V3、最小权限、脚本注入、DOM 内容提取、localStorage、异步请求、技能标签、折叠评分依据与复制反馈。不要声称做了复杂前端框架或跨浏览器自动化测试。

### AI 应用 / Agent 岗

突出模型输入边界、候选人资料真实性约束、证据提取与确定性评分分工、结构化输出、严格校验和异常处理。当前是单次分析工作流，不应包装成自主 Agent、多智能体系统、RAG 或模型训练项目。

## 可量化数字的使用规则

可以写：

- 响应包含总分、五维 `score_breakdown`、四类技能、候选人证据、建议、理由与 greeting 等结构化字段。
- JD 与候选人资料各限制为最多 8,000 字符。
- 发布回归 pytest 44 项通过，另有 Node 提取与 popup 测试。
- Node 测试覆盖智能提取、选区优先、长度上限、新旧响应渲染、loading、自动滚动和复制反馈等行为。

不要编造用户数、准确率、节省时间比例、站点覆盖数、调用量或简历通过率。若未来获得真实数据，再补充统计口径、样本量和测量时间。
