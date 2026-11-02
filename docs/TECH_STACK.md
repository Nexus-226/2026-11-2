# 技术栈与开发边界

> 基于架构指南形成的团队约定草案，供 A、B、C 评审。当前实现状态以本表为准；未经实现的内容不能按已接通展示。

原始架构指南第 9 节的 A/C 角色与当前团队决定相反；本文和任务表统一采用 A：Agent、B：后端、C：前端。

| 部分 | 技术约定 | 负责人 | 当前状态 |
|---|---|---|---|
| 前端 | React 19、TypeScript 5.7、Vite 6；npm，依赖锁定见 `frontend/package-lock.json` | C | 宠物资料和聊天页面支持演示；真实接口联调待做 |
| 后端入口 | Python 3.10+、FastAPI、Pydantic、Uvicorn | B | 健康检查、宠物 CRUD、对话路由和统一错误响应已实现 |
| Agent | Python 模块放在 `backend/app/agent/`；白名单工具、Pydantic 参数校验；LLM 通过 Provider 抽象 | A | Runtime、宠物工具、对话编排和 MockProvider 已实现；真实 LLM 待接入 |
| 业务服务 | Service 组织业务，外部系统使用独立 Adapter | B；LLM Provider 由 A 与 B 对齐 | 宠物与对话 Service 已实现；地图适配待做 |
| 数据库 | SQLite + SQLAlchemy 2 + Alembic 迁移 | B | 宠物、会话和消息已持久化；启动时由 Alembic 应用迁移 |
| 地图（P1） | 高德开放平台；后端 Web 服务查询 POI，前端地图展示 | B 后端，C 前端，A 工具调用 | 未接入；Key、配额与服务权限待团队准备 |
| 测试 | 后端 pytest + HTTPX；前端 Vitest + Testing Library + jsdom，另有构建检查 | 各负责人 | 后端宠物、Agent 和对话接口有测试；前端有聊天交互与 API Client 测试 |
| 协作 | Git 短分支 + PR，按 `docs/PR_GUIDE.md` 评审 | 全员 | 指南已入库 |

## 依赖方向

```text
前端 C → FastAPI 路由 B → Agent A → 白名单工具 A → 服务 B → 数据库/外部适配器 B
                        └──────────────────────→ 服务 B
```

- 宠物、对话和地点等业务数据由前端通过 FastAPI 获取；P1 可使用地图厂商的浏览器 SDK 渲染地图。后端 Web 服务密钥和 LLM 密钥不放到前端或 Git；浏览器地图 Key 使用独立配置和限制，不与后端 Web 服务 Key 混用。
- Agent 不直接执行模型生成的代码、SQL、Shell 或任意 URL；工具经过参数校验并调用服务。LLM Provider 抽象归 A，连接和错误边界与 B 对齐。
- 三方响应先在适配层转换为项目内部结构；前端和 Agent 不依赖高德原始字段。
- P0 先采用单用户本地演示，不实现登录和用户隔离；上线前必须重新设计认证、权限和数据隔离。
- `.env.example` 当前只是变量名示例，程序还不读取它；不能把它视为密钥管理已完成。

## 版本与待确认事项

- 模型供应商、模型名称、Key 和部署方式由 A/B 根据实际可用资源决定；接口不依赖某一家。
- 包版本以各自依赖文件及前端锁文件为准；Python 依赖当前是范围约束，尚无锁文件。
- 地图 Key、浏览器地图 SDK 与后端 Web 服务的申请和配额需在 P1 开发前确认。
- 三天演示可先使用明确标注的种子地点；完整 P1 的真实附近服务仍需高德接入与验收。详见 [任务表](TASKS.md)。
- API 契约见 [API.md](API.md)，当前仓库与指南的差距见 [REPOSITORY_STATUS.md](REPOSITORY_STATUS.md)。
