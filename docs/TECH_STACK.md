# 技术栈与开发边界

> 基于架构指南形成的团队约定草案，供 A、B、C 评审。当前实现状态以本表为准；未经实现的内容不能按已接通展示。

原始架构指南第 9 节的 A/C 角色与当前团队决定相反；本文和任务表统一采用 A：Agent、B：后端、C：前端。

| 部分 | 技术约定 | 负责人 | 当前状态 |
|---|---|---|---|
| 前端 | React 19、TypeScript 5.7、Vite 6；npm，依赖锁定见 `frontend/package-lock.json` | C | 宠物资料和聊天页面支持演示；真实接口联调待做 |
| 后端入口 | Python 3.10+、FastAPI、Pydantic、Uvicorn | B | 健康检查、宠物 CRUD、对话路由和统一错误响应已实现 |
| Agent | Python 模块放在 `backend/app/agent/`；白名单工具、Pydantic 参数校验；LLM 通过 Provider 抽象 | A | Runtime、宠物工具、对话编排及 Qwen/Mock Provider 已实现；跨请求历史上下文待修复（P0-8） |
| 业务服务 | Service 组织业务，外部系统使用独立 Adapter | B；LLM Provider 由 A 与 B 对齐 | 宠物与对话 Service 已实现；地图适配待做 |
| 数据库 | SQLite + SQLAlchemy 2 + Alembic 迁移 | B | 宠物、会话和消息已持久化；启动时由 Alembic 应用迁移 |
| 日常记录与站内提醒（P1） | 复用现有分层和数据库；具体字段/接口由 P1-7 确认 | B 数据服务，C 页面，A 只读工具 | 全部未开始；不等同于已有宠物备注或聊天记录 |
| 地图（P1） | 高德开放平台；后端 Web 服务查询 POI，前端地图展示 | B 后端，C 前端，A 工具调用 | 未接入，POI 尚未查通；Key、配额与服务权限在地图开发前确认 |
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
- `.env.example` 只是示例，不会被直接加载；LLM 配置已读取环境变量，并在 python-dotenv 可用时加载本地 `.env`。有 LLM_API_KEY 使用 Qwen，否则使用 MockProvider；真实密钥不能提交。

## 版本与待确认事项

- 已接入 DashScope OpenAI 兼容接口，默认 qwen-plus，使用现有 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL 配置；接口保留 Provider 抽象，部署方式仍需按实际资源确认。
- 包版本以各自依赖文件及前端锁文件为准；Python 依赖当前是范围约束，尚无锁文件。
- P1 全部未开始，实施顺序为日常记录、站内提醒、Agent 查询、附近服务；P2 增强项见任务表。地图 Key、浏览器 SDK 与后端 Web 服务的申请和配额在地图开发前确认，不阻塞记录主线。
- 地图阶段可先使用明确标注的种子地点；完整附近服务仍需高德接入与验收，不能将地图演示数据描述为实时查询。详见 [任务表](TASKS.md)。
- API 契约见 [API.md](API.md)，当前仓库与指南的差距见 [REPOSITORY_STATUS.md](REPOSITORY_STATUS.md)。
