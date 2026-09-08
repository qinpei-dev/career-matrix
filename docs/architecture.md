# CareerMatrix 架构

> AI-Powered Career Intelligence & Decision System

## 全栈拓扑

```mermaid
flowchart TB
    subgraph Client["Client"]
        Web["Next.js Web UI"]
        Extension["Manifest V3 Extension"]
    end

    subgraph Compose["Docker Compose"]
        Frontend["frontend<br/>Next.js :3000"]
        Backend["backend<br/>FastAPI :8000"]
        Postgres[("postgres<br/>PostgreSQL 16 + pgvector")]
        Volume[("postgres_data<br/>named volume")]
    end

    subgraph Intelligence["Application Pipeline"]
        CRUD["Jobs / Profiles / Documents"]
        RAG["Resume Parsing + RAG Retrieval"]
        Agent["Career Copilot Agent Workflow"]
        Scoring["Deterministic Scoring"]
        Provider["LLM / Embedding Provider"]
    end

    Web --> Frontend --> Backend
    Extension --> Backend
    Backend --> CRUD
    Backend --> RAG
    Backend --> Agent
    CRUD --> Postgres
    RAG --> Postgres
    Agent --> RAG
    Agent --> Scoring
    Agent --> Provider
    Postgres --- Volume
```

浏览器访问 `localhost:3000`，客户端请求使用 `NEXT_PUBLIC_API_BASE_URL` 访问 `localhost:8000`；Next.js 服务端渲染在 Compose network 内使用 `http://backend:8000`。Backend 通过内部服务名 `postgres:5432` 连接数据库，宿主机不需要知道容器 IP。

## Backend 分层

```mermaid
flowchart LR
    API["FastAPI Routes"] --> Application["Application Services"]
    Application --> Repositories["Repositories"]
    Application --> Documents["Document Processing"]
    Application --> Retrieval["Retrieval Service"]
    Application --> Agent["Agent Service"]
    Agent --> Workflow["Career Copilot Workflow"]
    Workflow --> Retrieval
    Workflow --> Scoring["Deterministic Scoring"]
    Repositories --> SQLAlchemy["SQLAlchemy Models"]
    Documents --> Embedding["Embedding Provider"]
    Retrieval --> Vector["pgvector"]
    SQLAlchemy --> DB[("PostgreSQL")]
    Vector --> DB
```

| 层 | 职责 |
| --- | --- |
| API | HTTP 契约、请求校验、依赖注入与错误映射 |
| Application | CRUD、文档处理、检索、分析与 Agent 生命周期编排 |
| Agent Workflow | 校验输入、提取要求、检索证据、评分、生成并保存结果 |
| Infrastructure | SQLAlchemy、PostgreSQL、pgvector、LLM 与 Embedding provider |
| Scoring | 使用固定状态映射与权重计算结果，不允许模型自由决定最终分数 |

## Agent 与 RAG 数据流

```mermaid
sequenceDiagram
    participant UI as Next.js UI
    participant API as FastAPI
    participant Agent as Agent Workflow
    participant RAG as Retrieval Service
    participant DB as PostgreSQL + pgvector
    participant LLM as LLM Provider

    UI->>API: POST /api/v1/agent/runs
    API->>Agent: 创建受控运行
    Agent->>DB: 读取 Job / Profile
    Agent->>LLM: 提取岗位要求
    Agent->>RAG: 检索候选人证据
    RAG->>DB: pgvector 相似度搜索
    DB-->>RAG: Resume chunks
    RAG-->>Agent: Evidence
    Agent->>Agent: 确定性评分
    Agent->>LLM: 生成解释与建议
    Agent->>DB: 保存 steps / analysis / evidence
    UI->>API: GET /api/v1/agent/runs/{id}
    API-->>UI: 状态、步骤、结果与证据
```

## Docker 启动顺序

```mermaid
flowchart LR
    Pull["Pull / Build Images"] --> PG["Start postgres"]
    PG --> PGHealth{"postgres healthy?"}
    PGHealth -->|yes| API["Start backend"]
    API --> APIHealth{"backend healthy?"}
    APIHealth -->|yes| UI["Start frontend"]
    UI --> UIHealth{"frontend HTTP 200?"}
    UIHealth -->|yes| Ready["CareerMatrix Ready"]
```

Compose 不自动执行 migration。命令行用户显式运行 Alembic；`start_demo.bat` 是为兼容保留名称的本地初始化入口，会在服务启动后执行 `upgrade head`，并仅在本地开发用户表为空时 Seed。

## 数据与安全边界

- `.env` 与 `.env.docker` 被 Git 和 Docker build context 排除。
- API Key 只进入 Backend 运行环境，不写入 Frontend、Extension 或镜像层。
- PostgreSQL 使用 named volume 持久化；`docker compose down` 不删除数据。
- PostgreSQL 宿主机端口仅绑定 `127.0.0.1`。
- Backend 与 Frontend 使用非开发启动命令；两个服务都有 healthcheck。
- Extension / Native Host 只负责浏览器采集与本地控制，不承担 RAG、Agent 或评分职责。
- 当前是本地运行架构，没有公网 TLS、正式鉴权、密钥托管、备份策略或高可用设计。
