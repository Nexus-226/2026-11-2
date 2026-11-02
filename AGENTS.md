# 给项目开发助手的说明

本文件适用于整个仓库。先阅读 README 和与任务相关的文档；用户的具体要求优先于本文件。

## 分工与范围

- A 负责 `backend/app/agent/`、Agent 工具协议和 LLM 接入；B 负责 FastAPI、业务服务、数据库与外部服务适配；C 负责 `frontend/` 和交互。
- P0 聚焦宠物资料与 Agent 对话闭环；附近宠物服务地图为 P1。不要把预留目录或接口草案描述成已实现功能。
- 变更前查看现有文件和工作区状态，保留他人未提交的工作。按任务范围修改，不为无关功能提前堆叠占位实现。

## 架构与接口

- 前端通过 FastAPI 通信；Agent 只调用已注册且经过参数校验的工具；工具通过 Service 使用数据库或外部服务。避免跨层直连。
- 接口以 [docs/API.md](docs/API.md) 为准；其中宠物资料的生日和备注字段已决定，其余部分仍待团队评审。技术选型和实现状态见 [docs/TECH_STACK.md](docs/TECH_STACK.md) 与 [docs/REPOSITORY_STATUS.md](docs/REPOSITORY_STATUS.md)。实现或调整接口时，同步相关 Schema、前端类型、文档与适当的测试。
- P0 宠物资料的生日和备注字段已确定为 `birthday`、`notes`，不新增 `age`、`health_notes`；生日不详时可在备注记录大概年龄，不能推测具体生日。其他接口约定仍需团队评审。
- P0 对话草案为 `POST /api/v1/chat`，普通 JSON 请求和回复；地图相关路径为 P1。不要自行把 SSE 或地图接入设为 P0 前提。
- Agent 不执行模型输出的代码、SQL、Shell 或任意 URL；不要把第三方原始响应直接作为项目内部模型。
- 不提交真实密钥、`.env`、数据库文件、精确定位或真实对话数据；`.env.example` 只能包含安全示例。

## 验证与协作

- 遵守根目录 `.editorconfig` 的编码、换行和缩进约定；提交前检查未跟踪文件，避免带入本地 IDE 配置。
- 开始任务时核对 [docs/TASKS.md](docs/TASKS.md)；提 PR 时更新对应任务的状态和链接，合并且验证后再标记已完成。接口、启动方式或实现状态变化时同步相应文档。
- 后端依赖安装及启动方式见 README；后端改动按需运行 `python -m pytest backend/tests`。
- 前端依赖安装后，在 `frontend/` 运行 `npm run build`；涉及交互时补充与风险相称的测试。
- Python 使用 Ruff，前端使用 Prettier；按 README 的检查命令验证，格式化时只处理本次改动的文件，不批量重排 Markdown。ESLint 暂未配置。
- 不依赖真实 LLM 或地图配额的测试应使用模拟响应；若无法运行检查，要说明原因和未验证范围。
- 按 [docs/PR_GUIDE.md](docs/PR_GUIDE.md) 小步提交与评审；只在实际完成并验证后更新实现状态。
