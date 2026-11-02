# Pet Agent

三人协作的宠物助手项目。当前前端提供宠物资料演示页面，后端提供健康检查；宠物资料与后端的真实联调、Agent 对话等功能尚待开发。

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

开发前请先评审：[技术栈与分层约定](docs/TECH_STACK.md)、[接口契约草案](docs/API.md) 和 [仓库现状与缺项](docs/REPOSITORY_STATUS.md)。Git 协作见 [PR 指南](docs/PR_GUIDE.md)。

项目优先级：P0 先完成宠物资料与 Agent 对话闭环；P1 再加入附近宠物服务。负责人、依赖、状态和审核安排见 [项目任务表](docs/TASKS.md)。

## 技术栈

| 部分 | 约定 | 当前状态 |
|---|---|---|
| 前端 | React + TypeScript + Vite | 宠物资料页面支持本地演示；真实接口联调和其他页面待开发 |
| 后端 | Python + FastAPI + Pydantic | 已有应用入口和健康检查；业务接口待开发 |
| Agent | Python Agent 模块、受控工具和 LLM Provider | 目录已预留；模型和工具接入待开发 |
| 数据 | SQLite + SQLAlchemy 2 + Alembic | 技术选型草案；依赖、模型和迁移尚未配置 |
| 地图（P1） | 高德开放平台 | 尚未接入；Key 和配额待准备 |

LLM 供应商和具体模型尚未确定。前端锁定的依赖版本见 `frontend/package-lock.json`，详细选型和边界见 [技术栈文档](docs/TECH_STACK.md)。

## 接口速览

业务接口使用 `/api/v1` 前缀；以下是供三人评审的草案，**除健康检查外尚未实现**。

| 接口 | 用途 | 阶段 |
|---|---|---|
| `GET /health` | 服务健康检查 | 已实现 |
| `GET /api/v1/pets`、`POST /api/v1/pets` | 查询列表、新建宠物 | P0 |
| `GET /api/v1/pets/{pet_id}`、`PATCH /api/v1/pets/{pet_id}`、`DELETE /api/v1/pets/{pet_id}` | 查看、修改、删除宠物 | P0 |
| `POST /api/v1/chat` | Agent 对话，第一版暂定 JSON 回复 | P0 |
| `GET /api/v1/nearby`、`GET /api/v1/places/{place_id}` | 附近服务查询和地点详情 | P1 |

宠物字段、错误格式、A/B 工具边界和地图参数以 [接口契约草案](docs/API.md) 为准。契约需三人评审；实现时如有变更，同步更新文档和测试。

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

宠物资料页默认使用本地演示数据，仅保存在当前浏览器，不会同步后端。B 的宠物 CRUD 接口完成后，在 `frontend/.env.local` 中设置 `VITE_PET_DATA_SOURCE=api` 并重新启动前端，即切换到 `/api/v1/pets`；接口失败时页面显示错误，不会自动回退到演示数据。切换模式不会迁移已有演示资料。

`.env.example` 仅列出后续接入可能需要的配置；骨架暂不读取这些变量。真实密钥和本地数据库不要提交到 Git。

## 检查

```powershell
# 项目根目录，已安装后端 dev 依赖
python -m pytest backend/tests

# frontend 目录，已安装依赖
npm run build
```

P0 后续需实现宠物资料 CRUD、SQLite、Agent 对话和工具调用；P1 再接入高德附近地点查询与地图页面。
