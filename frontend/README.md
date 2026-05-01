# TravelPlanner Frontend

Vue 3 + Vite 前端应用，负责旅行需求填写、Agent 规划进度展示和行程结果渲染。

## Setup

```powershell
npm install
Copy-Item .env.example .env
```

## Environment

`frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_AMAP_KEY=your_web_js_api_key
VITE_AMAP_SECURITY_JS_CODE=your_security_js_code
```

## Scripts

```powershell
npm run dev
npm run typecheck
npm run lint
npm run test:unit
npm run test:e2e
npm run build
```

## Main Flow

`HomePage` 收集旅行需求，`PlanningPage` 消费后端 SSE 进度流，`PlanResultPage` 展示最终行程、地图路线、天气、餐饮和下载入口。
