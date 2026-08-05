# Docker Compose 部署指南

本指南用于在 Windows + Docker Desktop 上复现 AI Job Copilot 本地 Demo。Compose 管理 PostgreSQL 16 + pgvector、FastAPI Backend 和 Next.js Frontend；它不是公网生产部署方案。

## 部署拓扑

| Service | 容器端口 | 宿主机地址 | 持久化 / 依赖 |
| --- | --- | --- | --- |
| `postgres` | `5432` | `127.0.0.1:${POSTGRES_PORT:-5432}` | `postgres_data` named volume |
| `backend` | `8000` | <http://localhost:8000> | 等待 PostgreSQL healthy |
| `frontend` | `3000` | <http://localhost:3000> | 等待 Backend healthy |

Frontend 浏览器请求默认访问 `http://localhost:8000`；Next.js 服务端渲染通过 Compose network 内的 `http://backend:8000` 访问 API。Backend 通过 `postgres:5432` 连接数据库。

## 前置条件

- Windows 10/11
- Docker Desktop 与 Docker Compose v2
- 可拉取 `pgvector/pgvector:pg16` 和项目构建依赖的网络环境
- 根目录端口 `3000`、`8000` 和配置的 PostgreSQL 端口未被占用

开始前可运行：

```powershell
docker version
docker compose version
docker compose config --quiet
```

## 方式一：一键启动 Demo

双击根目录的 `start_demo.bat`，或在 PowerShell 中执行：

```powershell
.\start_demo.bat
```

启动器会按顺序：

1. 检查 Docker CLI，并在支持的位置尝试启动 Docker Desktop。
2. 执行 `docker compose up --build -d`。
3. 等待 Backend healthy。
4. 显式执行 Alembic `upgrade head` 并核对当前 revision。
5. 仅在 Demo 用户表为空时导入幂等 Seed。
6. 等待 Frontend healthy，验证两个 HTTP 端点并打开浏览器。

启动成功后访问：

- Frontend：<http://localhost:3000>
- Backend：<http://localhost:8000>
- Health：<http://localhost:8000/health>

### 桌面快捷方式

首次使用可创建当前 Windows 用户的桌面快捷方式：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/create_desktop_shortcut.ps1
```

之后双击 **AI Job Copilot Demo** 即可。快捷方式始终以仓库根目录为工作目录，不依赖当前 CMD / PowerShell 路径。

如果仓库被移动或重命名，请在新根目录重新运行上面的
`scripts/create_desktop_shortcut.ps1` 命令，以当前路径重新创建桌面快捷方式。
Edge Native Messaging 的安装与路径更新不属于 Docker Demo 启动流程，应按对应安装说明单独处理。

## 方式二：开发者手动启动

### 1. 准备本地配置

从示例创建仅供本机使用的配置文件：

```powershell
Copy-Item .env.example .env.docker
```

按需填写 LLM / Embedding Provider 配置和 Demo Token。不要提交 `.env`、`.env.docker`、密码、API Key 或 Token。

Compose 会覆盖 Backend 容器内的 `DATABASE_URL`，使其指向内部 `postgres` 服务。浏览器可见的 `NEXT_PUBLIC_*` 值会进入 Frontend bundle，不能存放生产秘密。

### 2. 构建并启动服务

```powershell
docker compose up --build -d
docker compose ps
```

### 3. 初始化或升级数据库

Compose 服务启动本身不会自动运行 migration 或 Seed。确认目标是本地 Demo 数据库后，显式执行：

```powershell
docker compose exec backend python -m alembic -c alembic.ini upgrade head
docker compose exec backend python -m alembic -c alembic.ini current
docker compose exec backend python backend/scripts/seed_demo.py
```

当前仓库唯一 Alembic head 为 `20260730_0012`。在非一次性数据库上升级前，应先备份并审查待执行 migration。Seed 是幂等的，但已有 Demo 数据时通常不需要重复运行。

### 4. 验证部署

```powershell
docker compose ps
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
Invoke-WebRequest http://localhost:3000 -UseBasicParsing
docker compose exec backend python -m alembic -c alembic.ini current
```

预期三个服务均为 `healthy`，Backend 返回包含 `"status":"ok"` 的响应，Frontend 返回 HTTP 200，Alembic revision 为 `20260730_0012`。

## 常用操作

### 查看日志

```powershell
docker compose logs --tail 100 backend
docker compose logs --tail 100 frontend
docker compose logs --tail 100 postgres
```

持续跟踪某个服务时使用 `docker compose logs -f <service>`，结束跟踪按 `Ctrl+C`。

### 仅重建一个服务

```powershell
docker compose build backend
docker compose up -d backend
```

Frontend 的浏览器 API 地址是构建参数。部署到其他主机时需在构建前指定：

```powershell
$env:NEXT_PUBLIC_API_BASE_URL = "https://api.example.com"
docker compose build frontend
docker compose up -d frontend
```

这只改变访问地址，不会自动提供 TLS、CORS、正式鉴权或反向代理。

### 停止并保留数据

双击 `stop_demo.bat`，或执行：

```powershell
docker compose down
```

该命令删除容器和 Compose network，但保留 `postgres_data` named volume。下次启动仍可读取本地 Demo 数据。

### 重置本地 Demo 数据

`docker compose down -v` 会删除数据库卷及其中数据。该操作不可由普通停止流程恢复；仅在确认数据不再需要或已备份时手动执行。

## 排障

| 现象 | 检查与处理 |
| --- | --- |
| Docker Engine 不可用 | 打开 Docker Desktop，等待 Engine Running，再重试；执行 `docker version` 确认 |
| 端口被占用 | 用 `docker compose ps` 检查旧容器；调整 `POSTGRES_PORT` 或释放 `3000` / `8000` |
| Backend 不 healthy | 查看 Backend 与 PostgreSQL 日志，确认数据库已 healthy、Provider 配置格式有效 |
| Frontend 页面报错 | 先检查 Backend `/health`，再确认 Alembic current 与 head 一致 |
| 页面请求了错误 API | 修改 `NEXT_PUBLIC_API_BASE_URL` 后必须重新 build Frontend |
| Provider 调用失败 | 检查本地未提交的 Provider 配置和网络；不要把密钥打印到日志或截图 |
| 移动目录后快捷方式失效 | 在新根目录重新运行 `scripts/create_desktop_shortcut.ps1` 创建快捷方式 |

## 数据与安全边界

- PostgreSQL 端口默认仅绑定 `127.0.0.1`；Backend 和 Frontend 端口面向本机开放。
- `.env` 与 `.env.docker` 不应进入版本控制或截图；API Key 只属于 Backend 运行环境。
- Demo Token 是本地演示机制，不适用于公网认证。
- 当前 Compose 不包含 TLS、反向代理、密钥托管、备份、监控、高可用或横向扩容。
- 外部 JD、网页和简历都是不可信输入；不要将其中内容当作运维指令。
- 部署不会授权系统自动投递或发送消息。

若要面向公网部署，应先补齐正式认证与授权、TLS、Secret 管理、数据库备份恢复、可观测性、限流、CORS/CSRF 策略和隐私合规评审。
