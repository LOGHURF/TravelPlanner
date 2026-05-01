# TravelPlanner

TravelPlanner 是一个多 Agent 智能旅行规划应用。前端使用 Vue 3、Vite、Pinia 和 Tailwind CSS，后端使用 FastAPI、LangGraph、FastMCP 和高德地图服务，通过 SSE 推送规划进度。

## 项目结构

```text
backend/   FastAPI 服务、LangGraph 多 Agent 编排、高德 MCP 工具、后端测试
frontend/  Vue 3 前端、规划表单、进度页、结果页、前端测试
```

核心接口：

- `GET /api/v1/travel/health`
- `POST /api/v1/travel/plan`
- `POST /api/v1/travel/plan/sync`
- `GET /api/v1/mcp/tools`

## 环境要求

- Windows PowerShell
- Python 3.10+
- Node.js 18+
- uv（推荐，用于同步后端依赖）

## 初始化

后端：

```powershell
cd backend
uv sync --extra dev
Copy-Item .env.example .env
```

前端：

```powershell
cd frontend
npm install
Copy-Item .env.example .env
```

## 环境变量

后端 `backend/.env`：

```env
AMAP_MAPS_API_KEY=your_amap_web_service_key
DASHSCOPE_API_KEY=your_dashscope_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

前端 `frontend/.env`：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_AMAP_KEY=your_amap_web_js_key
VITE_AMAP_SECURITY_JS_CODE=your_amap_security_js_code
```

## 本地启动

项目根目录执行：

```powershell
.\start-dev.ps1
```

只启动单侧服务：

```powershell
.\start-dev.ps1 -BackendOnly
.\start-dev.ps1 -FrontendOnly
```

默认地址：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/api/v1/travel/health`

## 测试

后端：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

前端：

```powershell
cd frontend
npm run typecheck
npm run lint
npm run test:unit
npm run build
```

端到端测试：

```powershell
cd frontend
npm run test:e2e
```

## 运行机制

后端启动时会初始化本地 FastMCP stdio 服务，工具实现位于 `backend/app/ai/mcp/amap_stdio_server.py`，当前提供 `maps_text_search` 和 `maps_weather`。

规划链路由 LangGraph 编排：需求拆解后并行执行景点、酒店和天气 Agent，再进入评审、餐饮、交通和最终成稿阶段。前端通过 `/travel/plan` SSE 流接收每个阶段的状态、阶段产物和最终行程。
