# 仓库核对：骨架与待办

核对范围：架构指南第 6–8 节和当前 `main` 上已合并的项目骨架。文件或空目录存在，不等于对应功能已经实现。

| 项目 | 当前状态 | 下一步 |
|---|---|---|
| React + TypeScript + Vite | 宠物资料和聊天页面支持演示，已预留 API Client | C 与 A/B 联调真实接口 |
| FastAPI | `GET /health`、宠物 CRUD 和 `/api/v1/chat` 已实现；错误格式和参数校验有测试 | 与 C 完成前后端联调，后续实现地图路由 |
| Agent 与工具 | Runtime、宠物资料工具、对话编排和 MockProvider 已实现 | A 接入真实 LLM Provider |
| 业务和数据 | SQLite/SQLAlchemy 已持久化宠物、会话和消息；Alembic 迁移已配置 | B 实现 P1 地图服务 |
| 会话和模型 | 前端聊天演示、后端 MockProvider 对话接口可用；真实模型尚未接通 | A 接真实 LLM，C 与 A/B 联调聊天界面 |
| 地图（P1） | 前后端目录已预留，尚未接入 | B 接高德和附近 API，C 做定位/地图/列表，A 接附近工具 |
| 文档和配置 | README、PR 指南、技术栈和 API 草案、`.env.example` 已有 | 按评审更新契约；实现配置读取，不能提交真实密钥 |
| 格式化、CI、前端测试 | 已有 Ruff、Prettier 和前端聊天测试；CI 尚未配置 | 按改动运行对应检查；联调后补充真实接口相关测试 |

宠物 CRUD、SQLite Alembic 迁移、验证错误、会话消息持久化和 MockProvider 对话接口已实现；真实模型接入及前后端取消/超时联调尚未完成。指南中的 Docker Compose 标注为可选，目前未配置。

宠物资料的 `birthday`、`notes` 字段已决定；其他接口和技术选型见 [API.md](API.md) 与 [TECH_STACK.md](TECH_STACK.md)，仍需三人评审确认。
