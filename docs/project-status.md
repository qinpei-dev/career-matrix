# CareerMatrix 项目状态

> AI-Powered Career Intelligence & Decision System

本页按当前源码描述功能。真实 Provider、浏览器和 Docker 运行态必须在目标环境另行验收；历史报告中的测试数量不能作为当前结果。

| 模块 | 状态 | 源码依据及边界 |
| --- | --- | --- |
| 本地身份与用户隔离 | PARTIAL | `core/demo_auth.py` 使用配置的 Bearer Token，API 服务按用户过滤；不是生产级账号认证 |
| 岗位管理及 fingerprint 幂等 | IMPLEMENTED | `api/v1/jobs.py`、`application/job_fingerprint.py` |
| 简历上传、PDF/DOCX 解析和持久化 | IMPLEMENTED | `api/v1/documents.py`、`application/document_service.py` |
| Candidate Profile / Profile Draft | IMPLEMENTED | `api/v1/profiles.py`、`application/profile_draft_service.py`；草稿需人工确认 |
| Embedding / RAG / pgvector | IMPLEMENTED | `application/retrieval_service.py` 与数据库向量适配；真实 Provider 质量 UNVERIFIED |
| 多维分析和确定性评分 | IMPLEMENTED | `application/analysis_service.py`、`services/scoring.py` |
| Agent Workflow | PARTIAL | 固定节点和步骤持久化；中断运行标记失败，没有步骤级续跑或 exactly-once LLM 保证 |
| AnalysisTask | IMPLEMENTED | `application/analysis_task_service.py` 的 CAS、claim、lease、retry/recovery；PostgreSQL 并发行为需单独验证 |
| 定制简历 | PARTIAL | 生成、证据约束编辑、版本、DOCX 导出已实现；PDF 返回 501 |
| Next.js 工作区 | IMPLEMENTED | 岗位、简历、资料、分析、设置页面；真实浏览器 E2E UNVERIFIED |
| 扩展与 Native Host | PARTIAL | Manifest V3、采集与 Windows/Edge 本地控制有代码和自动化测试；扩展 API 请求需要本地 Demo Token，真实 Native Host 生命周期本轮失败 |
| Docker Compose 本地栈 | PARTIAL | 配置检查可运行；完整冷启动和数据库运行态本轮未验证 |
| 正式账号、多人协作、自动投递 | NOT IMPLEMENTED | 当前不在本地 Demo 范围 |

## 安全边界

Provider Key 仅由 Backend 使用。浏览器中的 Demo Token 是公开给本地客户端的演示凭据，不可用于公网身份认证。采集网页、JD 和简历按不可信内容处理；生成结果和评分必须人工核对。系统不会自动发送邮件、招聘消息或投递。

## 文档与迁移

当前 Alembic 唯一 head 为 `20260730_0012`，对应 `tailored_resumes`。早期 `20260724_0010` 对应 `analysis_task_claim_lease`。版本和历史验收材料保留供追溯，不代表本页所述的当前状态。
