# Pet Agent

Pet Agent 是一个三天黑客松项目：先完成“宠物资料 CRUD → 个性化对话”的可靠闭环，再扩展附近宠物医院、洗护店和用品店查询。

## 范围与优先级

- **P0（必须）**：固定演示用户的宠物资料增删改查、后端内运行的 Agent、基于宠物资料的个性化聊天、清楚的失败提示。
- **P1（P0 稳定后）**：附近宠物服务的地图/列表、WGS-84 到 GCJ-02 边界处理、定位拒绝后的手动地址回退。
- **延期**：流式输出（SSE）、登录、多 Agent、长期位置历史和真实地图供应商接入。

> Agent 是 FastAPI 后端内的 Python 模块，只能调用进程内登记的白名单工具/服务。前端只调用 FastAPI；Agent 不调用前端，也不通过 HTTP 绕回 B 的接口。

## 目录

```text
frontend/   React + TypeScript + Vite（C：前端与演示）
backend/    FastAPI、数据/地图服务（B）和进程内 Agent（A）
docs/       架构、接口和三天任务清单
```

## 快速启动

要求：Python 3.11+、Node.js 20+。

### 后端

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

后端地址为 `http://localhost:8000`，OpenAPI 文档为 `http://localhost:8000/docs`。

### 前端

```bash
cd frontend
npm install
npm run dev
```

复制 `.env.example` 为 `.env` 可调整 API 地址。演示用户固定为 `demo-user`，仓库内置一只名为“团子”的演示宠物。

## 测试与检查

```bash
cd backend && pytest
cd frontend && npm run test
cd frontend && npm run build
```

## 三分钟演示

1. 打开“宠物资料”，读取并修改“团子”，或新建一只宠物。
2. 切到“个性化聊天”，选择宠物并提问“它最近应该注意什么？”。
3. 展示回答引用宠物资料；再问医疗问题，确认出现兽医风险提示。
4. 若 P0 已稳定，打开“附近服务”，使用定位或手动地址展示模拟地点列表。

详细约定见 [架构](docs/ARCHITECTURE.md)、[API](docs/API.md) 与 [任务清单](docs/TASKS.md)。
