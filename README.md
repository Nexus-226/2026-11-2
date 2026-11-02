# Pet Agent

三人协作的宠物助手项目。前端提供宠物资料和聊天演示页面，后端提供健康检查、宠物资料 CRUD 和基于 MockProvider 的 Agent 对话接口；真实 LLM 接入、前后端完整联调与附近服务仍待完成。

## 目录与分工

```text
frontend/                     C：React + TypeScript 前端
  src/app/                    入口与应用
  src/pages/                  对话、宠物资料、附近服务页面
  src/components/             chat / map / common 组件
  src/api/ hooks/ types/ styles/
  tests/
backend/                      Python + FastAPI 后端
  app/agent/                  A：Agent Runtime、提示词与工具
  app/api/ core/ schemas/     B：路由、配置和数据结构
  app/services/ db/           B：业务服务和数据访问
  app/integrations/           B：第三方适配
  migrations/ tests/
docs/                         架构、接口及技术决策
scripts/                      开发辅助脚本
```

A 负责 Agent、工具协议和 LLM 接入；B 负责后端 API、数据库与业务服务；C 负责前端和交互。LLM Provider 的边界由 A、B 共同确定。前端通过 FastAPI 访问后端；Agent 通过受控工具和服务访问数据及外部能力。地图查询是 P1，目录预留不代表功能已完成。

原始《Pet Agent 架构与开发指南》第 9 节将 A、C 的职责写反；本仓库以当前明确的 **A：Agent、B：后端、C：前端** 分工为准。

开发前请先评审：[技术栈与分层约定](docs/TECH_STACK.md)、[接口契约草案](docs/API.md) 和 [仓库现状与缺项](docs/REPOSITORY_STATUS.md)。Git 协作见 [PR 指南](docs/PR_GUIDE.md)。

项目优先级：P0 先完成宠物资料与 Agent 对话闭环；P1 再加入附近宠物服务。负责人、依赖、状态和审核安排见 [项目任务表](docs/TASKS.md)。

## 技术栈

| 部分 | 约定 | 当前状态 |
|---|---|---|
| 前端 | React + TypeScript + Vite | 宠物资料和聊天页面支持演示；真实接口联调待完成 |
| 后端 | Python + FastAPI + Pydantic | 健康检查、宠物资料 CRUD、统一错误响应、对话路由和会话消息持久化已实现 |
| Agent | Python Agent 模块、受控工具和 LLM Provider | Agent Runtime、宠物工具、对话编排和 MockProvider 已接入；真实模型待接入 |
| 数据 | SQLite + SQLAlchemy 2 + Alembic | 本地演示用户与宠物资料通过 SQLite/SQLAlchemy 持久化；Alembic 迁移已配置 |
| 地图（P1） | 高德开放平台 | 尚未接入；Key 和配额待准备 |

LLM 供应商和具体模型尚未确定。前端锁定的依赖版本见 `frontend/package-lock.json`，详细选型和边界见 [技术栈文档](docs/TECH_STACK.md)。

## 接口速览

业务接口使用 `/api/v1` 前缀：

| 接口 | 用途 | 阶段 |
|---|---|---|
| `GET /health` | 服务健康检查 | 已实现 |
| `GET /api/v1/pets`、`POST /api/v1/pets` | 查询列表、新建宠物 | P0，已实现 |
| `GET /api/v1/pets/{pet_id}`、`PATCH /api/v1/pets/{pet_id}`、`DELETE /api/v1/pets/{pet_id}` | 查看、修改、删除宠物 | P0，已实现 |
| `POST /api/v1/chat` | Agent 对话，JSON 回复；当前使用 MockProvider | P0，路由与会话存储已实现 |
| `GET /api/v1/nearby`、`GET /api/v1/places/{place_id}` | 附近服务查询和地点详情 | P1 |

宠物字段、错误格式、A/B 工具边界和地图参数以 [接口契约](docs/API.md) 为准。SQLite 数据默认写入运行目录下的 `pet_agent.db`，可用 `PET_AGENT_DATABASE_URL` 修改连接地址。除已决定的宠物字段外，其余接口约定仍需三人评审；实现时如有变更，同步更新文档和测试。

宠物资料的字段已决定：P0 使用可为空的 `birthday` 和 `notes`，不新增 `age`、`health_notes`。生日不详时可在 `notes` 写大概年龄，不推测生日；其他接口约定仍需评审。

## 启动

需要 Python 3.10+ 和 Node.js 20.19+（或 22.12+）。在项目根目录分别运行：

```powershell
# 后端
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e "./backend[dev]"
python -m uvicorn app.main:app --app-dir backend --reload
```

访问 `http://127.0.0.1:8000/health`，应返回 `{"status":"ok"}`。

```powershell
# 前端：另开终端
cd frontend
npm install
npm run dev
```

前端地址以 Vite 的终端输出为准。开发时 `/api` 和 `/health` 会代理至 `http://127.0.0.1:8000`，可通过前端环境变量 `VITE_API_PROXY_TARGET` 修改代理目标。

宠物资料页默认使用本地演示数据，仅保存在当前浏览器，不会同步后端。在 `frontend/.env.local` 中设置 `VITE_PET_DATA_SOURCE=api` 并重新启动前端，即切换到 `/api/v1/pets`；前后端仍需完成联调。接口失败时页面显示错误，不会自动回退到演示数据。切换模式不会迁移已有演示资料。

聊天页默认显示固定的演示回复，不连接真实模型，聊天记录只保留在当前页面。在 `frontend/.env.local` 设置 `VITE_CHAT_DATA_SOURCE=api` 并重启前端，即可切换到已实现的 `POST /api/v1/chat`；当前后端使用 MockProvider，不会生成真实模型回复，请求失败时前端也不会自动生成模拟回复。若对话需要关联宠物，还应设置 `VITE_PET_DATA_SOURCE=api`，并启动后端：本地演示宠物的 ID 不能用于后端对话接口。

取消操作只停止前端等待，服务端可能仍在处理；超时或中断后重试可能产生重复请求。前后端仍需联调会话 ID、宠物 ID、错误格式和取消行为。

`.env.example` 仅列出后续接入可能需要的配置；数据库连接可通过环境变量 `PET_AGENT_DATABASE_URL` 设置。真实密钥和本地数据库不要提交到 Git。

## 检查

```powershell
# 项目根目录，已安装后端 dev 依赖
python -m pytest backend/tests

# frontend 目录，已安装依赖
npm run build
npm test
```

Python 使用 Ruff 做检查与格式化，前端使用 Prettier；版本分别固定在 `backend/pyproject.toml` 和 `frontend/package-lock.json`。对本次改动的文件单独运行命令，例如：

```powershell
# 项目根目录：把路径换成实际改动的 Python 文件
python -m ruff check backend/app/main.py
python -m ruff format --check backend/app/main.py
python -m ruff format backend/app/main.py

# frontend 目录：把路径换成实际改动的前端文件
npm run format:check -- src/app/App.tsx
npm run format -- src/app/App.tsx
```

本 PR 不批量格式化现有文件。`frontend/.prettierignore` 排除了生成文件、锁文件和 Markdown。ESLint 尚未配置，待 C 开发业务页面时确定规则。

`.gitattributes` 让 Git 新检出或重新写入的文本文件使用 LF，即使本机设置了 `core.autocrlf=true`；已有工作区文件不会立即自动转换。请先保存本地改动，再按需用编辑器或对应格式化工具转换涉及的文件。

应用启动时会自动执行 Alembic `upgrade head`。开发环境也可在 `backend/` 目录手动运行 `python -m alembic upgrade head`。宠物资料 CRUD、Agent 对话路由和会话消息持久化已实现；P0 后续需接入真实 LLM 并完成前后端联调；P1 再接入附近地点查询和地图页面。
