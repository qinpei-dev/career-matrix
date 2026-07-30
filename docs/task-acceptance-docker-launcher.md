# AI Job Copilot 2.0 项目任务验收表

## 1. 基本信息

- 项目名称：AI Job Copilot 2.0
- 功能名称：Demo 启动脚本自动检测并启动 Docker Desktop
- 验收日期：2026-07-30（Asia/Shanghai）
- Git 分支：`main`
- 当前仓库 HEAD：`a6c9e5086a5a6e1b51e2a2f78252190756ff148c`
- 对应 commit：`c01fdf419cce252432c6caa3695fa3fbcfbd323f`（`chore(demo): auto start docker desktop in launcher`）
- 验收结论：**PASS**

结论依据为指定 commit 的真实 diff、当前代码静态检查，以及仓库内
`docs/demo-acceptance-report-2026-07-24.md` 保存的实际冷启动证据。本次没有重新运行
`start_demo.bat`，当前 Docker Engine 也未运行；相关运行结果均明确标记为
**HISTORICAL EVIDENCE**，不冒充本次复测。

## 2. 任务目标

原始问题：Docker Desktop 未启动时运行 `start_demo.bat`，会出现无法连接
`dockerDesktopLinuxEngine` 的 named-pipe 错误，普通用户难以据此恢复。

预期结果：

- 自动判断 Docker Engine 是否可用。
- Docker Desktop 未启动时自动启动。
- 等待 Docker Engine 就绪。
- Docker 正常后继续原有 Demo 启动流程。
- 超时后给出清晰提示。
- 不向启动器用户直接泄漏难以理解的底层 named-pipe 错误。

## 3. 不可修改范围

本任务明确禁止修改：

- Backend 业务逻辑
- Frontend 业务逻辑
- RAG
- Agent
- Embedding
- 数据库业务模型
- Job fingerprint
- AnalysisTask 状态机
- API Key 和环境密钥
- Docker Compose 整体架构

指定 commit 的 diff 只涉及两个启动脚本，未触及上述范围；`docker-compose.yml`、
`README.md` 和 `DOCKER.md` 也未被该 commit 修改。

## 4. AI 实际修改文件

数据来自
`git diff --numstat c01fdf419cce252432c6caa3695fa3fbcfbd323f^ c01fdf419cce252432c6caa3695fa3fbcfbd323f`。

| 文件 | 修改目的 | 主要改动 | 新增 | 删除 | 是否超出范围 |
| --- | --- | --- | ---: | ---: | --- |
| `scripts/start_demo.ps1` | 在进入 Compose 流程前恢复 Docker Engine 可用性 | 新增 Engine 探测和轮询函数；检查 Desktop 进程；探测系统级及用户级安装位置；用 `Start-Process` 启动；每 5 秒轮询、最多 120 秒；抑制预期的原生 Docker 错误；失败时提供恢复指引；Engine 就绪后继续原流程 | 81 | 3 | 否 |
| `start_demo.bat` | 让双击入口调用增强后的 PowerShell 启动器并执行正常构建流程 | 仍通过 PowerShell 调用 `scripts/start_demo.ps1`，移除原来的 `-NoBuild` 参数 | 1 | 1 | 否 |

commit 汇总为 82 行新增、4 行删除。当前 HEAD 中这两个文件相对指定 commit
没有后续差异。

## 5. 实现流程

实际代码流程如下：

1. 先确认 Docker CLI 存在，并用 `docker version` 探测 Engine。
2. Engine 不可用时，检查名为 `Docker Desktop` 的进程是否存在。
3. 若进程不存在，依次查找 Docker Desktop 的系统级和当前用户级常见安装路径。
4. 找到可执行文件后使用 `Start-Process` 启动 Docker Desktop。
5. 每 5 秒通过 `docker info` 检查 Engine。
6. 最多等待 120 秒，截止后再做最后一次探测。
7. Engine 就绪后运行 `docker version` 验证，并继续原有 Compose 构建、迁移、Seed、
   健康检查及 HTTP 验证流程。
8. 超时后提示用户打开 Docker Desktop、等待显示 Engine Running，并重新运行
   `start_demo.bat`。
9. `start_demo.bat` 从项目根目录调用 PowerShell 启动脚本，并传递退出码。

## 6. 执行的测试命令

### 本次验收（2026-07-30）

| 命令 | 结果 | 分类 |
| --- | --- | --- |
| `docker version` | Client 29.6.1；Engine 未运行，Server 检查失败 | CURRENT CHECK |
| `docker info` | Engine 未运行，检查失败 | CURRENT CHECK |
| `docker context ls` | PASS；当前 context 为 `desktop-linux` | CURRENT CHECK |
| `docker compose config --quiet` | PASS；exit code 0 | CURRENT CHECK |
| `docker compose ps` | Engine 未运行，失败 | CURRENT CHECK |
| 请求 `http://localhost:3000` | 当前不可用 | CURRENT CHECK |
| 请求 `http://localhost:8000/health` | 当前不可用 | CURRENT CHECK |
| `python -m alembic -c alembic.ini heads` | PASS；当前唯一 head 为 `20260724_0010` | CURRENT CHECK |
| `git diff --check` | PASS（创建本文档前的仓库检查） | CURRENT CHECK |
| `git status --short` | 已检查 | CURRENT CHECK |

本次未运行 `start_demo.bat`，因为它会启动 Docker Desktop、构建服务并执行数据库迁移，
超出本次只做文档取证所需的最小变更范围。

### 仓库历史记录（2026-07-24）

以下命令或结果来自仓库已提交的
`docs/demo-acceptance-report-2026-07-24.md`，本次未重新执行：

- `start_demo.bat`
- `docker info`
- `docker compose config --quiet`
- `docker compose ps`
- `docker compose exec -T backend python -m alembic -c alembic.ini current`
- `http://localhost:3000`
- `http://localhost:8000/health`

以上全部标记为 **HISTORICAL EVIDENCE**，不表示 2026-07-30 重新执行通过。

## 7. 测试结果

| 测试场景 | 预期结果 | 实际结果 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| 1. Docker Desktop 已关闭 | 可在 Engine 不可用的冷启动状态运行入口 | 历史验收先正常停止 Desktop，并确认 `docker info` 无法连接 Engine | PASS（HISTORICAL EVIDENCE） | `docs/demo-acceptance-report-2026-07-24.md` §4 |
| 2. 自动检测 Engine 不可用 | 启动器进入恢复分支 | 历史冷启动进入自动恢复；当前代码用 `docker version` 的退出码判断 | PASS（HISTORICAL EVIDENCE + CODE REVIEW） | 历史报告 §4；指定 commit diff |
| 3. 自动启动 Docker Desktop | 找到安装后自动启动 | 历史输出 `Docker Desktop is not running. Starting Docker Desktop...`；代码调用 `Start-Process` | PASS（HISTORICAL EVIDENCE + CODE REVIEW） | 历史报告 §4；`scripts/start_demo.ps1` |
| 4. 等待信息每隔约 5 秒输出 | 等待时持续给出可理解状态 | 代码每轮失败后输出等待信息并休眠 5 秒；历史报告记录出现等待信息 | PASS（HISTORICAL EVIDENCE + CODE REVIEW） | `Wait-ForDockerEngine`；历史报告 §4 |
| 5. Engine 在合理时间内就绪 | 就绪后继续启动 | 已提交历史报告记录第一次 5 秒轮询后可用，完整冷启动约 40 秒；任务上下文另称约 15 秒，两项记录不一致，不合并为单一精确耗时 | PASS（HISTORICAL EVIDENCE） | 历史报告 §4；任务提供的历史记录 |
| 6. 120 秒超时分支 | 停止等待并输出恢复指引 | 静态检查确认 120 秒截止、最终探测和三条恢复指引；本次及历史报告均未证明实际等待到超时 | NOT VERIFIED（运行态）；静态实现符合 | 指定 commit diff |
| 7. `docker compose config` | Compose 配置有效 | 本次 `docker compose config --quiet` exit code 0 | PASS | CURRENT CHECK |
| 8. PostgreSQL healthy | 容器健康 | 历史验收为 `healthy`；本次 Engine 未运行，未复测 | PASS（HISTORICAL EVIDENCE） | 历史报告 §5 |
| 9. Backend healthy | 容器健康 | 历史验收为 `healthy`；本次 Engine 未运行，未复测 | PASS（HISTORICAL EVIDENCE） | 历史报告 §5 |
| 10. Frontend healthy | 容器健康 | 历史验收为 `healthy`；本次 Engine 未运行，未复测 | PASS（HISTORICAL EVIDENCE） | 历史报告 §5 |
| 11. Alembic migration head | 运行库 revision 与当时 head 一致 | 当时 `current == head == 20260723_0008`；当前仓库唯一 head 已是 `20260724_0010`，本次未验证运行库 current | PASS（当时，HISTORICAL EVIDENCE）；CURRENT RUNTIME NOT VERIFIED | 历史报告 §2；本次 `alembic heads` |
| 12. Frontend HTTP 200 | 首页可访问 | 历史验收 HTTP 200；本次因 Engine 未运行而不可用 | PASS（HISTORICAL EVIDENCE） | 历史报告 §5 |
| 13. Backend health HTTP 200 | 返回 200 和 `{"status":"ok"}` | 历史验收符合；本次因 Engine 未运行而不可用 | PASS（HISTORICAL EVIDENCE） | 历史报告 §5 |
| 14. named-pipe 错误不直接暴露 | 启动器只显示可操作提示 | 探测函数将 Docker 原生 stdout/stderr 重定向为空；历史冷启动未出现原始 named-pipe 错误直接退出 | PASS（HISTORICAL EVIDENCE + CODE REVIEW） | `Test-DockerEngine`；历史报告 §4 |

历史环境记录为 Docker Engine Client/Server 29.6.1、Docker context
`desktop-linux`、PostgreSQL/Backend/Frontend 均 healthy、Frontend HTTP 200、Backend
`/health` HTTP 200 且响应 `{"status":"ok"}`。其中 Alembic `20260723_0008`
只代表 2026-07-24 当时的 head；当前仓库 head 是 `20260724_0010`。

## 8. 发现的问题

- Docker CLI 存在不代表 Docker Engine 已启动。
- Docker Desktop 启动需要等待，不能立即执行 Compose。
- Docker Desktop 可能存在系统级和用户级安装路径。
- 原始 named-pipe 错误对普通用户不友好。
- 固定等待 120 秒并不适合所有性能较慢的机器。
- 当前脚本主要面向 Windows 和 Docker Desktop。
- 运行态 120 秒超时路径没有可追溯的实际执行证据。
- `DOCKER.md` 仍描述“未运行时打印指引”，没有完整反映自动启动行为；这不影响指定
  commit 的运行逻辑，但后续可单独修正文档。

## 9. 人工修复内容

### AI 生成或修改

依据指定 commit 的真实 diff，AI 修改了：

- `scripts/start_demo.ps1`：增加 Engine 探测、Desktop 进程和安装路径检查、自动启动、
  5 秒轮询、120 秒超时、清晰错误提示，并控制失败时是否建议查看 Compose 日志。
- `start_demo.bat`：继续调用 PowerShell 启动器，但去掉 `-NoBuild`，恢复正常构建启动。

没有证据表明 AI 修改了 Backend、Frontend、RAG、Agent、Embedding、数据库模型、
Compose 架构或环境密钥。

### 人工发现或确认

- 人工根据错误定位 Docker Desktop 未运行。
- 人工确认不得修改 Backend、Frontend 等业务模块。
- 人工要求增加自动启动和等待逻辑。
- 人工确认测试场景和提交范围。
- 人工决定仅提交两个启动脚本。

现有证据不能证明人工逐行编写了代码，因此不作该表述。

## 10. 最终验收结论

- 功能目标是否完成：是；历史冷启动证据和当前代码均支持自动检测、启动、等待和继续流程。
- 是否修改禁止范围：否；指定 commit 仅修改两个启动脚本。
- 是否通过主要自动化验证：是；Compose 配置本次通过，历史报告还记录了相关项目测试和构建通过。
- 是否通过实际启动验证：是，但属于 2026-07-24 的 **HISTORICAL EVIDENCE**，本次未重跑。
- 是否存在剩余限制：是；Windows/Docker Desktop 专用、固定 120 秒，以及超时运行态未实测。
- 是否允许提交：从验收证据看该功能 commit 可接受；本次文档按任务要求不 commit、不 push。
- 最终结论：**PASS**

该结论仅代表 Windows + Docker Desktop Demo 启动场景，不代表跨平台启动器已经完成。
120 秒超时分支的运行态仍为 **NOT VERIFIED**，不影响已有成功冷启动主路径的 PASS。

## 11. 已知限制

- Windows 专用。
- 依赖 Docker Desktop。
- Docker 安装路径探测可能受版本或自定义安装位置影响。
- 无法修复 Docker Desktop 自身损坏。
- 120 秒后停止等待；慢速机器可能仍未完成启动。
- 超时分支只有代码证据，没有实际 120 秒运行证据。
- 不属于生产环境服务编排工具。
- 当前环境 Engine 未运行，服务和 HTTP 健康状态本次没有复测。

## 12. 面试讲解摘要

双击 Demo 时，Docker Desktop 未启动会直接抛 named-pipe 错误。AI 只改了两个启动脚本，
增加 Engine 检测、自动启动和限时轮询，未碰业务模块。通过 diff、Compose 配置和历史冷启动、
健康检查及 HTTP 结果验收；主路径通过，超时实测仍待补。
