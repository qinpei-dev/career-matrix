# Web 功能审计与闭环报告（2026-07-30）

## 审计清单

| 页面/功能 | 修复前 | 主要缺口 | 后端基础 | 优先级 | 当前状态 |
|---|---|---|---|---|---|
| Dashboard | PARTIAL | 缺简历/任务/最近分析；含未来能力占位 | 有岗位、分析、文档、任务数据 | P0 | WORKING：后端聚合真实统计和最近记录 |
| 全局导航 | PARTIAL | 设置、搜索、通知禁用；Agent 标为未来 | 部分存在 | P0 | WORKING：全部入口可访问 |
| 岗位列表 | PARTIAL | 无搜索、筛选、排序、分页 | 有列表 API | P1 | WORKING：后端查询与前端控件接通 |
| 新增/重复岗位 | WORKING | 缺少完整列表联动体验 | 有 fingerprint 幂等 | P1 | WORKING：保留 URL/内容归一化与冲突恢复 |
| 岗位详情 | PARTIAL | 无编辑/删除；有“即将推出”假按钮 | 有读取 API | P0 | WORKING：编辑、二次确认删除，假按钮已移除 |
| 简历列表/上传 | PARTIAL | 无真实上传进度和明确 RAG 状态 | 有同步解析/Embedding | P1 | WORKING：传输进度真实，解析阶段不伪造百分比 |
| 文档详情 | PARTIAL | 失败不可重试；缺详情错误边界 | 有详情/分块/删除 | P1 | WORKING：重试、状态、Loading/Error/删除闭环 |
| RAG 检索 | WORKING | 未就绪时的状态不够明确 | 有向量检索 API | P1 | WORKING：仅 ready 且存在真实分块时开放 |
| AnalysisTask | WORKING | 前端结果维度展示不全 | 有完整状态机/API | P1 | WORKING：恢复、重试、人工确认和刷新持久化保留 |
| Agent Run | PARTIAL | 刷新恢复依赖 localStorage | 有持久化 Run/Step | P1 | WORKING：新增当前活跃 Run 后端恢复 |
| 匹配结果/求职辅助 | PARTIAL | 未完整展示优势、改进、面试与沟通稿 | 分析 JSON 已持久化 | P1 | WORKING：真实结果展示；沟通稿不自动发送 |
| 站内搜索 | PLACEHOLDER | 顶部输入框禁用 | 无聚合 API | P2 | WORKING：岗位、公司、简历名、分析结果 |
| 站内通知 | PLACEHOLDER | 铃铛禁用 | 可由持久化状态派生 | P2 | WORKING：任务/简历成功和失败状态 |
| 设置 | PLACEHOLDER | 入口禁用，无持久化 | 无 | P2 | WORKING：新增用户隔离的数据库设置 |
| Provider 状态 | MISSING | 无安全状态展示 | 有运行时配置 | P2 | WORKING：只返回布尔状态与脱敏文案 |
| 安全回归页 | WORKING | 无本次阻断缺口 | 有真实本地路径测试 | P1 | WORKING：保留 Mock 外部模型的明确边界 |
| Extension 采集/保存 | WORKING | 本次未发现断链 | 有真实 Jobs API | P1 | WORKING：原有测试保持通过 |

## 新增或修改的接口

- `GET /api/v1/jobs`：搜索、来源/分析状态筛选、排序、分页。
- `PATCH /api/v1/jobs/{job_id}`：用户隔离编辑并重算 fingerprint。
- `DELETE /api/v1/jobs/{job_id}`：拒绝删除存在活跃工作流的岗位，并事务清理终态关联记录。
- `POST /api/v1/documents/{document_id}/retry`：仅允许当前用户的失败文档重试。
- `GET /api/v1/agent/runs/active?job_id=...`：恢复当前用户岗位的活跃 Run。
- `GET /api/v1/workspace/dashboard`：真实工作区聚合视图。
- `GET /api/v1/workspace/search`：当前用户站内搜索。
- `GET /api/v1/workspace/notifications`：由持久化任务/文档状态派生通知。
- `GET/PATCH /api/v1/workspace/settings`：用户隔离设置。
- `GET /api/v1/workspace/providers`：仅返回脱敏 Provider 配置状态。

所有新增写接口使用现有 schema 校验、用户隔离和公开错误映射。前端不直接访问数据库。

## 数据库

- 新增 migration：`20260730_0011_user_settings`，父 revision 为 `20260724_0010`。
- 新表 `user_settings` 以 `user_id` 为主键并级联到 Demo 用户；保存显示名称、目标岗位、默认分析选项、每页数量和技术详情开关。
- 未修改任何已有 migration。
- Job fingerprint 与 AnalysisTask 的 CAS、version、claim token、lease、retry、recovery 约束未修改。

## 删除的误导入口

- 岗位详情“定制简历 · 即将推出”禁用按钮。
- Dashboard “未来能力/即将推出”卡片。
- Agent 导航中的“预览/未来”标记。
- 禁用的搜索框、通知按钮和设置按钮；均替换为真实功能。

## 明确保留的 OUT OF SCOPE

- 正式账号/鉴权/RBAC：当前 `X-User-Email` 仍是本地 Demo 身份方案。
- 自动投递、招聘站自动聊天、自动邮件/短信/推送：不在产品安全边界内。
- 真实第三方发送接口：仓库无基础设施，沟通稿只供人工复制和确认。
- 独立申请状态 CRM：现有仓库无该业务模型；本次不为扩大范围而重建数据库。
- 外部 Provider 可用性保证：设置页只显示脱敏配置状态，不主动泄露或探测密钥。

## 子 Agent 分工

- Dashboard/Nav：真实 Dashboard、搜索、通知、设置、Provider 脱敏状态。
- Jobs：岗位查询、编辑、删除、fingerprint 与关联数据保护。
- Documents：上传进度、失败重试、Embedding/RAG 状态、详情与删除。
- 主控：Analysis/Agent 恢复与结果展示、跨模块整合、全量/Docker/浏览器验收。
- QA/Security：独立 diff、安全、用户隔离、状态机、migration 和自动化测试审查。

## 已知限制与操作记录

- 文档处理仍是同步后端请求：浏览器可显示真实上传字节进度；上传完成后的解析/Embedding 阶段只显示不确定状态，不伪造进度。
- 站内通知是状态派生视图，不是邮件、短信或系统推送。
- 岗位分页采用 `page_size + 1` 判断下一页，不额外执行总数查询；Dashboard 聚合与站内搜索不受该页大小限制。
- QA 首次执行临时 SQLite 迁移时，PowerShell URL 覆盖出现非终止错误，导致该轮对当前配置 PostgreSQL 执行了 upgrade/downgrade/upgrade。未读取连接信息或秘密，命令成功且数据库回到 head；这是一次流程偏差，已如实记录。
