# TravelPlanner Vue 3 Frontend Refactor Plan

更新时间：2026-03-01

## 1. 项目目标

本次重构不是把 React 语法机械替换成 Vue，而是完成三件事：

1. 将现有前端从 `React + Vite` 重构为 `Vue 3 + TypeScript + Vite`。
2. 重新设计首页、规划中页面、结果页的整体视觉与信息架构。
3. 建立完整测试链路，覆盖单元、组件、端到端和真实联调烟测。

现有项目的核心业务流已经比较清晰：

1. 用户填写旅行需求。
2. 前端调用后端 `/api/v1/travel/plan`，通过 SSE 接收规划进度。
3. 规划完成后跳转到结果页，展示每日行程、天气、美食和地图路径。

因此，本次重构优先保留业务能力，重点升级前端架构、可维护性和视觉表达。

## 2. 参考网站与提炼结论

本次方案参考了以下公开站点的产品结构与界面信号：

1. Google Travel: https://travel.google.com/
2. Wanderlog: https://wanderlog.com/
3. Tripadvisor Trips: https://www.tripadvisor.com/Trips

从这些站点提炼出的有效信号如下：

1. `Google Travel` 的优势是搜索入口非常直接，导航负担很轻，首页更像“旅行控制台入口”而不是说明书。
2. `Wanderlog` 的优势是把“地图 + 行程 + 推荐”组织成一个连贯工作台，用户会感觉自己在操控一张旅行桌面。
3. `Tripadvisor Trips` 的优势是“保存、整理、AI 生成、协作”这些价值点表达得非常明确，但首屏更偏账户体系，弱化了即时创建。

本项目不照搬任何一个站，而是采用下面的折中策略：

1. 首页学习 `Google Travel` 的轻导航和强目的地入口。
2. 结果页学习 `Wanderlog` 的“地图与日程并置”结构。
3. 产品表达学习 `Tripadvisor Trips` 的“AI 规划 + 可整理”的价值传达方式。

## 3. 新的产品定位

新的前端定位为：

`一张带有旅行编辑感的智能行程桌面`

它不做 OTA 式大卖场，也不做花哨的大模型演示页，而是强调：

1. 快速输入需求。
2. 清楚看到规划过程。
3. 直接进入可执行的每日计划。
4. 地图路径、住宿建议、餐饮与天气围绕“当天决策”服务。

## 4. 设计方向

### 4.1 视觉主题

采用 `Editorial Atlas` 方向：

1. 视觉气质：地图册、旅行便签、登机牌、手工标注感。
2. 背景基调：暖白纸张底色 + 等高线纹理 + 局部坐标网格。
3. 主色：深海军蓝、暖沙色、朱砂红、雾青色。
4. 交互符号：路线虚线、坐标点、邮戳、卡片编号、章节标签。

### 4.2 设计原则

1. 首页不是“大横幅 + 普通表单”，而是一个带叙事感的旅行任务台。
2. 规划过程页不是传统进度条，而是“行程编排台”式状态面板。
3. 结果页不是信息瀑布流，而是“当天路线驱动”的阅读顺序。
4. 动效只服务两个目标：进入状态切换清晰，地图/卡片切换自然。

### 4.3 字体策略

中文场景优先可读性和气质，不用常见的系统堆栈做主视觉。

建议组合：

1. 标题：`Noto Serif SC` 或 `Source Han Serif SC`
2. 正文与 UI：`Noto Sans SC`
3. 数字与数据标签：`IBM Plex Mono`

## 5. 技术栈方案

基于 2026-03-01 本地 `npm view` 查询结果，建议使用：

1. `vue@3.5.29`
2. `vue-router@4.6.3`
3. `pinia@3.0.4`
4. `vite@7.3.1`
5. `@vitejs/plugin-vue@6.0.4`
6. `vitest@4.0.18`
7. `@vue/test-utils@2.4.6`
8. `playwright@1.58.2`
9. `vue-tsc@3.2.5`

新增技术决策：

1. `Vue 3 + Composition API + <script setup>`
2. `TypeScript` 作为默认代码语言
3. `Vue Router` 管理三段主路由
4. `Pinia` 管理规划会话、结果缓存和 UI 状态
5. 原生 CSS + CSS Variables，不引入重型 UI 组件库
6. `Vitest + Vue Test Utils` 做单元与组件测试
7. `Playwright` 做端到端测试和浏览器视觉验证

不引入 UI 组件库的原因：

1. 现有需求页面数不多，自研样式成本可控。
2. 这次重构重点是形成独特视觉语言，组件库会明显拉回模板化观感。

## 6. 路由与页面结构

计划采用以下路由：

1. `/`：首页与需求录入页
2. `/planning`：实时规划过程页
3. `/plan/:planId`：结果页
4. `/:pathMatch(.*)*`：404 回退到首页

### 6.1 首页

目标：快速开始规划，并让用户理解系统最终会给出什么结果。

模块：

1. 顶部导航：极简品牌与说明入口
2. Hero 区：旅行宣言、价值点、最近热门目的地卡片
3. Planner Composer：多段式需求录入区
4. Preview Rail：展示“每日路线 / 酒店 / 天气 / 美食”样例卡片
5. Trust Strip：说明路线、天气、住宿与推荐来源维度

### 6.2 规划中页面

目标：降低等待焦虑，让用户看到系统正在组织信息。

模块：

1. 当前旅行简报
2. 动态进度时间轴
3. 已返回数据快照：景点、酒店、天气、餐厅数量和缩略卡
4. 状态文案与错误重试
5. 页面底部保留“返回修改需求”

### 6.3 结果页

目标：以“当天安排”为核心，把地图和决策信息绑定。

模块：

1. 顶部概览 Hero：城市、日期、旅行画像、总览摘要
2. Day Switcher：天数切换导航
3. Daily Story Card：当天主路线、两个核心景点、酒店建议、费用估算
4. Map Board：当天两个核心景点路线
5. Weather & Dining Rail：天气与餐饮建议
6. Notes Board：整体建议、重要提醒、打包提示
7. 导出与返回操作

## 7. 组件与目录规划

新的目录建议：

```text
frontend/src/
  app/
    App.vue
    router.ts
    providers.ts
  assets/
    icons/
    patterns/
  components/
    common/
    planner/
    result/
    progress/
  composables/
    usePlanStream.ts
    useAmapRoute.ts
    useResponsive.ts
    usePlanPersistence.ts
  pages/
    HomePage.vue
    PlanningPage.vue
    PlanResultPage.vue
  services/
    api/
      client.ts
      planner.ts
    storage/
      planStorage.ts
  stores/
    planner.ts
    planResult.ts
  styles/
    tokens.css
    base.css
    utilities.css
  types/
    travel.ts
  utils/
    date.ts
    location.ts
    media.ts
    sse.ts
```

## 8. 状态管理设计

### 8.1 `planner` store

负责：

1. 当前表单数据
2. SSE 规划状态
3. 流式返回的 attractions / hotels / restaurants / weather / itinerary
4. 当前错误与重试逻辑

### 8.2 `planResult` store

负责：

1. 已生成计划缓存
2. `planId` 到 `plan + request` 的本地持久化
3. 当前激活日索引

### 8.3 数据流

1. 首页提交表单
2. `planner` store 保存请求并进入 `planning` 页
3. `usePlanStream` 建立 SSE 流
4. 规划结束后生成 `planId`，写入 `planResult` store + localStorage
5. 跳转到 `/plan/:planId`

## 9. 接口与兼容策略

保留现有后端接口约定：

1. `POST /api/v1/travel/plan`：SSE 流式规划
2. `GET /api/v1/travel/health`：健康检查

前端新增兼容处理：

1. `VITE_API_BASE_URL` 支持环境化接口地址，默认回退 `http://127.0.0.1:8000/api/v1`
2. 保留 `VITE_AMAP_KEY`
3. 保留 `VITE_AMAP_SECURITY_JS_CODE`
4. SSE 解析单独抽到 `utils/sse.ts`
5. 地图加载失败时回退为示意图，不阻塞结果页

## 10. 视觉系统细化

### 10.1 颜色

```text
--paper: #f6f1e8
--paper-strong: #ece1d1
--ink: #14233b
--ink-soft: #44536a
--route-red: #c14d3a
--sea-green: #5a8f87
--sun-gold: #d0a34a
--line: rgba(20, 35, 59, 0.12)
--shadow: 0 20px 60px rgba(25, 34, 52, 0.12)
```

### 10.2 主要卡片风格

1. 圆角不会过大，避免软萌感
2. 卡片带细描边、内阴影、纸张层叠感
3. 重点信息用章节标签和单色强调，不用大面积渐变按钮

### 10.3 动效

1. 首页加载：章节错落进入
2. 提交后：页面切换为“制图中”状态
3. 结果页切换天数：地图与日卡同步过渡
4. 所有动画控制在 180ms 到 420ms，避免拖沓

## 11. 重构阶段

### 阶段 A：基础架构迁移

1. 替换 React 依赖为 Vue 依赖
2. 改造 `vite.config`
3. 配置 TypeScript 与 `vue-tsc`
4. 建立 `router`、`stores`、`styles tokens`

交付标准：

1. Vue 首页能启动
2. `npm run build` 成功
3. `npm run typecheck` 成功

### 阶段 B：首页重做

1. 重写 Hero、Planner Composer、样例预览区
2. 重写日期、同行人、偏好、节奏、住宿选择
3. 建立表单校验与提交流程

交付标准：

1. 首页视觉完成
2. 表单行为与原业务一致
3. 通过组件测试

### 阶段 C：规划过程页

1. 抽离 SSE 流处理 composable
2. 完成实时状态、进度时间轴、预览面板
3. 错误态与重试逻辑接通

交付标准：

1. 能正确展示流式消息
2. 规划完成能跳转结果页
3. 通过端到端 mock 测试

### 阶段 D：结果页重做

1. 重写结果概览 Hero
2. 重写 Day Switcher 和 Daily Story Card
3. 重写地图板块与 fallback 逻辑
4. 重写天气、餐饮、说明区

交付标准：

1. 全部结果信息可见
2. 响应式在移动端和桌面端都稳定
3. 地图失败时有合理降级

### 阶段 E：测试与回归

1. 单元测试
2. 组件测试
3. Playwright 端到端
4. 本地联调与浏览器截图检查

## 12. 测试矩阵

### 12.1 单元测试

覆盖：

1. 日期格式化
2. SSE 事件解析
3. localStorage 持久化
4. 距离与时长格式化
5. 结果页文本拆分逻辑

### 12.2 组件测试

覆盖：

1. 首页表单必填校验
2. 偏好切换与人数增减
3. 规划状态时间轴渲染
4. 结果页切换天数后卡片内容变化

### 12.3 E2E 测试

覆盖：

1. 用户填写表单并提交
2. 前端接收模拟 SSE 流
3. 跳转结果页
4. 切换不同日期卡片
5. 响应式视口截图

### 12.4 真实联调烟测

覆盖：

1. 健康检查
2. 首页到规划页
3. 规划完成到结果页
4. 地图 key 缺失时 fallback

## 13. 当前已发现的环境阻塞

本地基线检查发现：

1. 前端 `http://127.0.0.1:5173` 当前可启动。
2. 后端当前未能直接启动。
3. 阻塞原因是后端配置中 `DEBUG` 被解析为字符串 `release`，而配置模型要求布尔值。

这意味着：

1. 前端重构可以先独立推进。
2. 端到端测试可以先用 Playwright mock SSE 保证前端闭环。
3. 真实联调阶段需要通过覆盖环境变量或修正本地配置来恢复后端。

## 14. 实施顺序

接下来实际执行按这个顺序：

1. 迁移前端脚手架到 Vue 3
2. 建立新的样式 token 和页面骨架
3. 完成首页与规划页
4. 完成结果页与地图
5. 补齐测试
6. 处理后端联调阻塞并做完整烟测

## 15. 本次重构的完成标准

满足以下条件才算完成：

1. React 依赖已完全移除
2. Vue 3 页面全部替换完成
3. 首页、规划页、结果页全部重新设计
4. 原有核心业务能力保留
5. 单元、组件、E2E、构建、类型检查全部通过
6. 浏览器端完成桌面端与移动端验证
