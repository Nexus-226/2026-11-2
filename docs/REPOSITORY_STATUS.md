# 仓库核对：骨架与待办

核对范围：架构指南第 6–8 节和当前 `main` 上已合并的项目骨架。文件或空目录存在，不等于对应功能已经实现。

| 项目 | 当前状态 | 下一步 |
|---|---|---|
| React + TypeScript + Vite | 已有入口、依赖与锁文件；构建通过 | C 实现页面、API Client、前端测试 |
| FastAPI | 已有应用入口和 `GET /health`，健康检查测试通过 | B 实现路由、统一错误、参数校验 |
| Agent 与工具 | `backend/app/agent/tools/` 目录已预留 | A 实现 Runtime、提示词、注册表、Schema、超时和调用次数限制 |
| 业务和数据 | services、db、integrations、migrations 目录已预留 | B 安装并配置 SQLAlchemy/Alembic，完成数据库、迁移、宠物 CRUD |
| 会话和模型 | 未实现 | A 接 LLM Provider；B 接会话存储和对话 API；C 接聊天页面 |
| 地图（P1） | 前后端目录已预留，尚未接入 | B 接高德和附近 API，C 做定位/地图/列表，A 接附近工具 |
| 文档和配置 | README、PR 指南、技术栈和 API 草案、`.env.example` 已有 | 按评审更新契约；实现配置读取，不能提交真实密钥 |
| 格式化、CI、前端测试 | 暂无统一配置 | 团队约定工具后逐步补充；当前只有前端 build 与后端健康检查测试 |

指南中列出的 `ChatPage.tsx`、`runtime.py`、`pet_service.py`、`alembic.ini` 等具体文件目前未创建；它们属于后续实现，并非已配置完成。指南中的 Docker Compose 标注为可选，目前未配置。P0 验收所需的宠物 CRUD、真实对话、错误处理、取消/超时及核心测试都尚未完成。

宠物资料的 `birthday`、`notes` 字段已决定；其他接口和技术选型见 [API.md](API.md) 与 [TECH_STACK.md](TECH_STACK.md)，仍需三人评审确认。
