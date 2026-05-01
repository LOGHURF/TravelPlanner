# Findings

## 仓库初看
- 根目录包含 `backend`、`frontend`、`docs` 和一份多 Agent 方案文档
- 后端存在 `langgraph.json`、`app/ai/graph_builder.py`、多个 `nodes/*_node.py`
- 初步判断核心实现基于 LangGraph 的固定图编排

## 已确认事实
- API 依赖注入直接返回 `app.ai.graph_builder.get_travel_graph()`，系统主干由单个 LangGraph 图驱动
- 实际 builder 是 `backend/app/ai/graph_builder.py`，不是方案文档中的更复杂版本
- 当前并行只有一处：`orchestrator -> attraction_agent + hotel_agent + weather_agent`
- `fan_in` 之后是固定串行：`reviewer -> restaurant -> transport -> final_planning`
- SSE 中的 agent start/done 主要是根据固定路由生成的前端事件，不代表存在独立自治的多 agent 运行时

## 节点能力判断
- orchestrator 主要是规则填充 state，不是基于上下文动态拆任务
- reviewer 虽然调用 LLM，但后续又被组合优化和规则逻辑覆盖，真实决策权偏低
- transport 和 final_planning 都存在明显规则兜底，因此整体更像“规则流水线 + 局部 LLM 修饰”
- 所有节点都通过同一个共享 `TripState` 传递结果，没有 agent 私有记忆、协商协议或冲突仲裁层

## 架构漂移
- `TravelPlanner_MultiAgent_方案.md` 设计了 budget/conflict/report 等更复杂角色，但真实代码未落地这些节点
- 方案文档中的目录结构是 `backend/agents`、`backend/graph`，真实代码在 `backend/app/ai/nodes` 与 `backend/app/ai/graph_builder.py`
- `backend/langgraph.json` 仍指向不存在的 `./app/graph/builder.py:travel`
- `backend/app/api/routers/travel.py` 的 `_resolve_next_agent_starts()` 认为 weather 在 transport 之后启动，但真实并行图里 weather 是 orchestrator fan-out 的并行节点
- `backend/app/ai/nodes/fan_in_node.py` 文档与检查逻辑只把 attraction/hotel 当 Phase-1 必需项，和真实图里 weather 一起 fan-in 也不完全一致

## 约束协同现状
- 请求模型有 `budget_per_person` 和 `total_budget` 概念，但运行图里没有预算 agent
- `orchestrator_node` 将 `state["total_budget"]` 固定写成 `0.0`
- `final_planning_node` 只是把估算费用写回最终结果，不做预算约束下的搜索、协商、重排或再规划
- 这意味着“预算”和“路径”之间不存在真实冲突协调，只存在结果生成后的展示字段

## 前端事实
- 前端 `planningAgents.ts` 预先写死了 agent 列表、阶段和权重
- 前端 store 只是消费固定事件类型并映射到固定卡片，不支持动态图拓扑或动态 agent 增减
- 因此前端展示的是“预设工作流可视化”，不是“真实多 agent 观察面板”

## 验证结果
- `backend/tests/test_fan_in.py` 通过
- `backend/tests/test_graph_builder.py` 失败，原因是测试仍断言 orchestrator 只 fan-out 到 2 个节点，但当前代码已经 fan-out 到 3 个节点（含 weather）
- 这说明架构实现、测试认知和系统文档已经发生漂移

## 2026-05-01 追加确认
- 前端提交 `days`，后端 `TripRequest` 使用 `duration=3` 默认值，导致传入 `days=7` 时后端仍计算为 3 天
- 当前系统环境变量 `DEBUG=release` 会使 `Settings.DEBUG: bool` 初始化失败；验证时需临时覆盖为 `false`，后续应从配置层规避外部变量污染
- `backend/app/ai/nodes/__init__.py` 导出 `weather_node`/`transport_node` 同名函数，导致 `from app.ai.nodes import weather_node as weather_service` 得到函数而不是模块
- 规划页保存结果后只设置 `savedPlanId`，不会自动 `router.push` 到结果页
- 前端状态图原来用线性顺序推断完成状态，导致某个后置串行节点完成时，未产出天气结果的并行天气节点也会显示为已完成
- 前端 `done` 事件原来无条件把进度设为 100%，如果流里先收到 error 再收到 done，会在视觉上掩盖失败
- 桌面截图发现日期组件在窄列里拆成两列后会竖排日期文本；已改为组件内部纵向布局，并用自定义触发器展示 `YYYY-MM-DD - YYYY-MM-DD`
- 景点搜索根因：prompt 要求 LLM 从 `110xxx` 风景名胜 types 里选择，且 `_clean_poi_to_attraction` 只接受 typecode 以 `11` 开头的 POI；这会把博物馆、艺术馆、展馆、历史街区、商业街区等可作为行程景点的高德 POI 过滤掉
- 修复方向：取消“types 必填/110 为全集”的假设，改为关键词优先；types 只在 LLM 明确知道高德代码吻合或请求显式限制时使用；清洗阶段只排除餐饮、住宿、交通、医疗、政府机构、公司等明显非景点类别
- 移动端完成页滚动根因：`TripLayout` 把 `@touchmove.prevent` 绑定在整个底部 sheet 容器上，内部 `overflow-y-auto` 内容区无法接收原生触摸滚动；修复为只在顶部手柄/标题区域处理拖拽，内容区使用独立 `flex-1 overflow-y-auto`
- 首页黑框根因：共用 `Input.vue` 内部 input 没有显式 `border-0`，会保留浏览器/Tailwind 表单预设边框；`outline-none` 计算后仍可能是透明 solid outline，截图里容易表现成原生焦点框
- 结果页雾化根因：`TripLayout.vue` 有覆盖全屏地图的 `rgba(248,250,252,...)` 线性渐变，`MapRouteBoard.vue` 内部还有覆盖地图容器的白色渐变；两层叠加导致地图像被雾罩住
- 结果页内容占比根因：桌面布局用网格为侧栏预留页面列，同时 `over-map` 默认渲染 Current Day 大卡和两个景点大卡；信息面板和地图覆盖内容重复，占用地图视野
- 结果页半截进入根因：路由没有 `scrollBehavior`，从首页底部提交按钮跳转后会保留原 scrollY，结果页地图顶部被滚出视口
- lint 失败根因：本地 Playwright 浏览器缓存 `.playwright-browsers` 位于 `frontend` 下，`eslint .` 会扫描其中的 Chrome 扩展源码；该目录属于生成产物，应从 ESLint 与 git 跟踪里排除
- 结果页侧栏顶部混乱根因：返回按钮、快捷标签放在同一个 `justify-between` flex 行里；侧栏宽度缩小时，返回按钮被压缩换行，标签被挤到多行且和按钮抢空间
- 当前 Day 规划“被压到后面”的根因：选中日程只有 `summaryText` 暗含在 overview 文案中，真正的 Day 信息在 `Days` 切换列表之后才进入景点/天气内容，缺少独立的 active-day 摘要区
- 地图内容透到侧栏后面根因：侧栏使用 `bg-white/95` 半透明背景，地图文字和道路会透出，造成“内容被压在后面/样式被覆盖”的视觉错觉
- 规划过程图覆盖根因：圆形节点、节点标签和 SVG 边都围绕同一中心坐标绘制，节点状态变化后文字高度增加，箭头会穿过文字或被圆点遮挡
- 规划过程图箭头不可读根因：节点间距小于节点视觉高度，边只剩很短线段；细 marker 箭头贴近节点边缘，视觉上像断线或被卡片吞掉
- 修复方向：节点改为固定尺寸卡片，文字收在卡片内；边使用贝塞尔曲线、白色底描边和固定尺寸大箭头；节点缩小并拉大层距，让边有独立可读空间
- 手绘曲线过度歪扭根因：主链路使用左右大幅摆动的 S 型贝塞尔控制点，虽然是曲线，但破坏了自上而下的方向感；应让主链路近垂直，只保留很轻的手绘弯曲，分支再承担横向弧线
- 线粗箭头细根因：边线 5/6px、底描边 14px，但 marker 只有 18px，视觉比例反了；应把线降到 3/4px、底描边降到 9px，并把 marker 提到 24px
- 成稿完成后未进入结果页的根因：后端原先先发送 `final_planning` 的 `agent_done`，再序列化并发送 `itinerary`；这允许前端短暂或永久进入“成稿已完成但最终行程未入库”的假完成态，顶部按钮也因依赖已保存的 planId 而不会出现
- 修复原则：最终成稿节点必须先验证并发送 `itinerary`，再发送 `agent_done`；如果没有 `itinerary_draft`，直接暴露错误，不允许把成稿节点标为完成
- 最终阶段 `LLM response did not contain a valid JSON object` 根因：`final_planning_node` 使用通用 `invoke_llm_json_async` 生成总结 JSON，但该通用工具没有像景点/酒店/餐饮节点一样给 `ChatQwen` 传 `model_kwargs={"response_format":{"type":"json_object"}}`，模型可能返回普通文本，从而在最终成稿阶段中断
- 规划图卡在“最终成稿执行中”的前端根因：`itinerary` 已经是最终产物，但前端 store 收到 `itinerary` 时只把整体 `step` 设为 completed，没有同步把 `final_planning` agent 标为 completed；如果页面在后续 `agent_done` 到达前跳转或保存快照，回放/当前图会保留“最终成稿执行中”
- 点击“查看行程”时报 `QuotaExceededError` 的根因：所有历史行程都写在单个 `localStorage` key 里，单条记录又同时保存完整 `plan` 和 `planningState.itinerary`，等于重复存最终行程；景点/酒店/餐饮里的图片字段和过程日志继续放大体积，多次生成后单 key 超过浏览器本地存储配额
- 修复方向：保存前压缩记录，删除重复的 `planningState.itinerary` 和大媒体字段；历史结果只保留最近 5 条；写入触发 quota 时按时间淘汰旧记录，当前记录仍过大才抛出明确错误
- 搜索仍偏窄的根因：景点 ReAct 一次把多个关键词合成一个 `keywords` 参数，命中足量候选后会自动早停；酒店/餐饮在用户没有显式指定 `types` 时仍把规则推导出的 typecode 传给高德，导致 POI 召回被默认类型过滤
- 修复方向：景点每个关键词独立搜索，并由 LLM 基于覆盖度决定是否结束；酒店/餐饮默认不传 `types`，只有请求显式提供 type 限制时才传；放宽召回后在清洗层严格排除非住宿、非餐饮 POI
