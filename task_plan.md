# 当前任务：稳定 TravelPlanner 生成链路并重修前端体验

## 目标
- 修复请求字段、图拓扑、SSE 进度、测试之间的漂移
- 去掉会淹没错误的生产兜底，让 MCP/LLM/无候选异常显性失败
- 修复规划状态图显示不正确、生成后不自动跳转的问题
- 重做日期选择组件和主要页面视觉，让表单与规划页更清晰可用

## ///

### /// 1 后端确定性契约
- [completed] 统一 `TripRequest` 的天数字段，前端改发 `duration`
- [completed] 对日期与 duration 不一致做明确校验
- [completed] 同步后端测试与前端类型

### /// 2 图拓扑与事件一致性
- [completed] 统一实际 graph 与 SSE agent start 顺序
- [completed] 修复 `langgraph.json`、旧 MCP 测试路径、nodes 包导出遮蔽
- [completed] 修复相关后端测试

### /// 3 异常显性化
- [completed] 新增规划异常类型
- [completed] 改造 LLM JSON 调用，不再返回默认值
- [completed] 改造景点节点，去掉静默空列表和 LLM 默认搜索兜底
- [completed] 放宽景点/酒店/餐饮检索策略，去掉默认 typecode 对 POI 召回的硬限制
- [completed] SSE 出错后发送 error 并终止，不再继续 done

### /// 4 前端流程和 UI
- [completed] 修复生成完成后自动保存并跳转结果页
- [completed] 修复结果保存超出 localStorage 配额导致“查看行程”中断
- [completed] 修正规划状态图的拓扑、状态推导和文案
- [completed] 重做日期选择组件，支持更直接的日期/天数操作
- [completed] 调整首页/规划页视觉层级，减少玻璃卡片堆叠和状态误导

### /// 5 验证
- [completed] `uv run pytest`
- [completed] `npm run typecheck`
- [completed] `npm run test:unit`
- [completed] `npm run build`
- [completed] `npm run test:e2e`
- [completed] 启动前端并做桌面/移动截图检查

## 约束
- 不创建新分支或 worktree
- 生产代码不写 Mock
- 不用兜底掩盖真实异常
- 每次行为修改优先补测试，再改实现

## 错误记录
- 默认系统环境存在 `DEBUG=release`，会导致后端 Settings 初始化失败。验证命令中临时设置 `$env:DEBUG='false'`。
