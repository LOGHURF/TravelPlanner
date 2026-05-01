# Multi-Agent 智能旅行规划系统
## 完整技术方案

> **技术栈**：LangChain · LangGraph · 高德MCP · DeepSeek · React  
> **核心亮点**：结构化表单输入 · 并行数据采集 · 约束冲突协调 · 实时流式前端展示  
> **参考效果**：携程AI助手风格，含偏好选择面板 / 地图 / 行程卡片 / 费用估算

---

关于路径规划方面的注意事项

> - 不需要给出详细的路径，只需要给出两点的整体建议，比如驾车需要多久，多远，步行需要多久多远
>
> - 然后如果需要使用railway，就以卡片的形式列出来，从哪到哪，多长时间，需不需要中转，从哪中转（点击展开需要给出具体的，中转的几班车的卡片信息），几点出发几点到
> - 

## 目录

1. [整体架构设计](#一整体架构设计)
2. [Agent 角色设计](#二agent-角色设计)
3. [LangGraph 图结构](#三langgraph-图结构)
4. [State 设计](#四state-设计)
5. [各节点实现](#五各节点实现)
6. [高德MCP 数据服务层](#六高德mcp-数据服务层)
7. [前端展示设计](#七前端展示设计)
8. [项目目录结构](#八项目目录结构)
9. [开发顺序](#九开发顺序)
10. [简历写法](#十简历写法)

---

## 一、整体架构设计

### 1.1 三阶段流程

```
┌─────────────────────────────────────────────────────┐
│  第零阶段：结构化偏好输入（前端表单）                  │
│                                                     │
│  出发地/目的地  +  日期选择                           │
│  同行伙伴：独自 / 家庭 / 情侣 / 朋友 / 老人           │
│  风格偏好：文化体验 / 自然风光 / 历史古迹（多选）       │
│  行程节奏：紧凑 / 适中 / 宽松                         │
│  住宿偏好：舒适型 / 高档型 / 豪华型                   │
│                    ↓ 直接映射为结构化 State，无需LLM解析│
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  第一阶段：并行数据采集 Fan-out                       │
│                                                     │
│  景点Agent ──┐                                       │
│  餐厅Agent ──┼──→ 高德MCP数据服务层 ──→ 结构化数据   │
│  住宿Agent ──┤                                       │
│  天气Agent ──┘                                       │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  第二阶段：约束冲突协调（Multi-Agent核心价值）         │
│                                                     │
│  预算Agent  → 检查总费用是否超预算 → 要求压缩方案     │
│  交通Agent  → 检查路线合理性 → 要求重排景点顺序       │
│  Orchestrator → 裁决冲突 → 输出平衡后的方案           │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  第三阶段：行程整合输出                               │
│                                                     │
│  报告Agent → 生成结构化每日行程 → 前端渲染            │
└─────────────────────────────────────────────────────┘
```

### 1.2 为什么这样设计是真正的 Multi-Agent

- **第零阶段**：结构化表单替代自然语言输入，用户点选偏好直接映射为 State 字段，Orchestrator 无需 LLM 解析，降低错误率
- **第一阶段**：4个Agent并行调用不同类型的MCP工具，体现Fan-out并行编排
- **第二阶段**：预算Agent和交通Agent会互相影响决策，Orchestrator需要裁决冲突，这是真实的Agent间协作，不是顺序流水线
- **第三阶段**：汇聚所有Agent的输出，生成最终方案

---

## 二、Agent 角色设计

### 2.1 各 Agent 职责

| Agent | 职责 | 可用MCP工具 | 输出 |
|-------|------|------------|------|
| 景点Agent | 根据**风格偏好+同行伙伴**搜索候选景点 | `search_poi`（type=景点） | 候选景点列表（含坐标、评分、图片） |
| 餐厅Agent | 搜索目的地特色餐厅 | `search_poi`（type=餐饮） | 候选餐厅列表（含人均、评分） |
| 住宿Agent | 根据**住宿偏好档次**搜索酒店 | `search_poi`（type=住宿） | 候选酒店列表（含价格区间、位置） |
| 天气Agent | 获取旅行日期天气 | `get_weather` | 每日天气（含出行建议） |
| 预算Agent | 检查总费用，结合**住宿偏好**决定压缩方向 | 无（纯逻辑） | 预算分配方案 / 超预算警告 |
| 交通Agent | 结合**行程节奏**检查路线合理性，规划每日路线 | `route_planning` | 每日路线顺序 / 耗时估算 |
| Orchestrator | 协调冲突，决定是否重新规划 | 无 | 裁决结果 / 触发重新协商 |
| 报告Agent | 整合所有输出，生成最终行程 | 无 | 结构化行程JSON |

### 2.2 约束冲突协调示例

**场景**：用户预算2000元，3天北京

```
第一阶段结果：
- 景点Agent：推荐故宫+颐和园+长城+鸟巢+798  （5个景点）
- 住宿Agent：推荐三里屯某酒店  （600元/晚 × 3 = 1800元）
- 餐厅Agent：推荐烤鸭+涮羊肉+簋街夜宵

第二阶段协调：
预算Agent 发现：
  住宿1800 + 景点门票约400 + 餐饮约600 = 2800元，超预算800元

预算Agent 向 Orchestrator 发出信号：
  "需要压缩住宿或减少景点，建议砍掉2个景点门票较贵的选项"

交通Agent 同时发现：
  "Day1安排故宫+颐和园，距离18km，加上游览时间根本来不及"

Orchestrator 裁决：
  1. 住宿降级到400元/晚（节省600元）
  2. 长城和鸟巢合并到同一天（位置相近）
  3. 删除798（与历史文化偏好不符）

最终输出平衡后的3天方案
```

---

## 三、LangGraph 图结构

### 3.1 图结构代码

```python
from langgraph.graph import StateGraph, END
from langgraph.pregel import Send

def build_travel_graph():
    graph = StateGraph(TravelState)

    # 注册所有节点
    graph.add_node("orchestrator",      orchestrator_node)
    graph.add_node("attraction_agent",  attraction_node)
    graph.add_node("restaurant_agent",  restaurant_node)
    graph.add_node("hotel_agent",       hotel_node)
    graph.add_node("weather_agent",     weather_node)
    graph.add_node("fan_in",            fan_in_node)       # 等待并行结果汇聚
    graph.add_node("budget_agent",      budget_node)
    graph.add_node("transport_agent",   transport_node)
    graph.add_node("conflict_resolver", conflict_resolver_node)
    graph.add_node("report_agent",      report_node)

    # 入口：Orchestrator 解析用户需求
    graph.set_entry_point("orchestrator")

    # 第一阶段：Fan-out 并行
    graph.add_conditional_edges(
        "orchestrator",
        lambda s: ["attraction_agent", "restaurant_agent",
                   "hotel_agent", "weather_agent"],   # 同时触发4个
    )

    # 并行结果汇聚到 fan_in
    for agent in ["attraction_agent", "restaurant_agent",
                  "hotel_agent", "weather_agent"]:
        graph.add_edge(agent, "fan_in")

    # 第二阶段：约束协调（并行）
    graph.add_conditional_edges(
        "fan_in",
        lambda s: ["budget_agent", "transport_agent"],
    )

    # 预算和交通Agent结果汇聚到冲突裁决
    graph.add_edge("budget_agent",   "conflict_resolver")
    graph.add_edge("transport_agent","conflict_resolver")

    # 冲突裁决：通过则进入报告，不通过则重新协调
    graph.add_conditional_edges(
        "conflict_resolver",
        route_after_conflict,
        {
            "resolved":  "report_agent",
            "replan":    "fan_in",       # 重新从汇聚点开始，带上修订约束
            "max_retry": "report_agent", # 最多重试2次，强制输出
        }
    )

    graph.add_edge("report_agent", END)
    return graph.compile()


def route_after_conflict(state: TravelState) -> str:
    if state["conflict_resolved"]:
        return "resolved"
    if state["replan_count"] >= 2:
        return "max_retry"
    return "replan"
```

### 3.2 图结构示意

```
orchestrator
     ↓  Fan-out（并行）
┌────┬────┬────┬────┐
景点  餐厅  住宿  天气
└────┴────┴────┴────┘
          ↓  Fan-in
        fan_in
     ↓  Fan-out（并行）
   ┌────┴────┐
 预算Agent  交通Agent
   └────┬────┘
        ↓  Fan-in
   冲突裁决Agent
        ↓（有环：冲突未解决时回到fan_in）
   报告Agent → END
```

---

## 四、State 设计

```python
from typing import TypedDict, List, Dict, Optional, Any

class TravelState(TypedDict):
    # ── 用户输入（来自结构化表单，无需LLM解析）──
    origin: str                  # 出发地，如"北京"
    destination: str             # 目的地，如"深圳"
    days: int                    # 天数
    budget: float                # 总预算（元）
    travel_dates: List[str]      # 出行日期列表，如["2025-06-01", "2025-06-02"]

    # 表单偏好字段（直接从前端点选映射）
    companions: str              # 同行伙伴："独自出行"|"家庭出行"|"情侣出行"|"朋友出行"|"老人同行"
    style_preferences: List[str] # 风格偏好（多选）：["文化体验","自然风光","历史古迹"]
    pace: str                    # 行程节奏："紧凑"|"适中"|"宽松"
    hotel_level: str             # 住宿偏好："舒适型"|"高档型"|"豪华型"

    # ── 第一阶段：采集结果 ──
    candidate_attractions: List[POI]    # 候选景点
    candidate_restaurants: List[POI]    # 候选餐厅
    candidate_hotels: List[POI]         # 候选酒店
    weather_forecast: List[WeatherDay]  # 天气预报

    # ── 第二阶段：约束分析 ──
    estimated_cost: Dict[str, float]    # 各项费用估算
    budget_status: str                  # "ok" | "over" | "tight"
    budget_suggestion: str              # 预算Agent的压缩建议
    route_issues: List[str]             # 交通Agent发现的路线问题
    route_suggestion: str               # 路线调整建议

    # ── 冲突协调 ──
    conflict_resolved: bool             # 冲突是否已解决
    replan_count: int                   # 重规划次数
    final_attractions: List[POI]        # 最终确定的景点
    final_hotel: POI                    # 最终确定的酒店
    daily_routes: List[DayRoute]        # 每日路线规划

    # ── 输出 ──
    itinerary: TravelItinerary          # 最终行程
    streaming_updates: List[str]        # 流式推送给前端的更新消息


class POI(TypedDict):
    id: str
    name: str
    type: str           # 景点/餐厅/酒店
    address: str
    location: Dict      # {lng, lat}
    rating: float
    price: float        # 人均/门票/房价
    image_url: str
    open_hours: str
    tags: List[str]

class WeatherDay(TypedDict):
    date: str
    weather: str        # 晴/多云/雨
    temperature: str    # 如 "18-26°C"
    suggestion: str     # 出行建议

class DayRoute(TypedDict):
    day: int
    date: str
    weather: WeatherDay
    morning: List[POI]
    afternoon: List[POI]
    dinner: POI
    hotel: POI
    route_distance: float   # 当日总路程km
    estimated_time: int     # 当日预计游览时间（小时）

class TravelItinerary(TypedDict):
    destination: str
    total_days: int
    total_budget_estimate: float
    budget_breakdown: Dict[str, float]
    daily_plans: List[DayRoute]
    tips: List[str]         # 出行小贴士
    booking_links: Dict     # 订票跳转链接
```

---

## 五、各节点实现

### 5.1 Orchestrator 节点（直接映射表单数据，无需LLM解析）

```python
def orchestrator_node(state: TravelState) -> TravelState:
    """
    表单数据已经是结构化的，Orchestrator 只做两件事：
    1. 根据偏好组合生成各 Agent 的搜索关键词
    2. 初始化流程控制字段
    """
    # 根据同行伙伴和风格偏好，生成景点搜索关键词
    keyword_map = {
        "情侣出行":  ["浪漫", "打卡", "网红"],
        "家庭出行":  ["亲子", "适合家庭", "儿童友好"],
        "老人同行":  ["无障碍", "舒适", "经典"],
        "朋友出行":  ["热门", "好玩", "拍照"],
        "独自出行":  ["特色", "小众", "安全"],
    }
    companion_keywords = keyword_map.get(state["companions"], [])
    state["search_keywords"] = state["style_preferences"] + companion_keywords

    # 根据住宿偏好设定酒店价格范围（预算Agent的约束条件）
    hotel_price_map = {
        "舒适型": (200, 500),
        "高档型": (500, 1000),
        "豪华型": (1000, 9999),
    }
    state["hotel_price_range"] = hotel_price_map.get(state["hotel_level"], (200, 500))

    # 根据行程节奏设定每日景点数量上限
    pace_map = {"紧凑": 5, "适中": 3, "宽松": 2}
    state["max_attractions_per_day"] = pace_map.get(state["pace"], 3)

    # 初始化流程控制字段
    state["replan_count"] = 0
    state["streaming_updates"] = []
    state["conflict_resolved"] = False

    return state
```

### 5.2 景点 Agent 节点

```python
def attraction_node(state: TravelState) -> TravelState:
    """
    调用高德MCP搜索景点
    搜索关键词和每日数量上限已由 Orchestrator 根据表单偏好预处理好
    """
    raw_attractions = await data_service.fetch_attractions(
        city=state["destination"],
        keywords=" ".join(state["search_keywords"]),  # 已由Orchestrator生成
        count=20
    )

    # 每日景点数量上限来自行程节奏（紧凑=5/适中=3/宽松=2）
    total_needed = state["days"] * state["max_attractions_per_day"]

    filter_prompt = f"""
    用户偏好：{state['style_preferences']}
    同行伙伴：{state['companions']}
    行程节奏：{state['pace']}（每天最多安排{state['max_attractions_per_day']}个景点）
    共需筛选：{total_needed}个景点（{state['days']}天行程）

    以下是搜索到的景点，请筛选出最符合偏好的{total_needed}个，按推荐优先级排序：
    {format_pois(raw_attractions)}

    输出JSON列表，每个景点包含：name, reason（推荐理由）, priority（1-5）
    """
    selected = llm.invoke(filter_prompt)

    state["candidate_attractions"] = merge_poi_data(
        raw_attractions, parse_json(selected.content)
    )
    state["streaming_updates"].append("✅ 已找到 {} 个推荐景点".format(
        len(state["candidate_attractions"])
    ))
    return state
```

### 5.3 预算 Agent 节点

```python
def budget_node(state: TravelState) -> TravelState:
    """
    估算总费用，判断是否超预算，给出压缩建议
    """
    # 费用估算
    hotel_cost = state["candidate_hotels"][0]["price"] * state["days"]
    attraction_cost = sum(a["price"] for a in state["candidate_attractions"][:state["days"]*2])
    meal_cost = state["days"] * 3 * 80   # 假设人均80元/餐
    transport_cost = state["days"] * 50  # 市内交通估算

    total_estimate = hotel_cost + attraction_cost + meal_cost + transport_cost

    state["estimated_cost"] = {
        "hotel": hotel_cost,
        "attractions": attraction_cost,
        "meals": meal_cost,
        "transport": transport_cost,
        "total": total_estimate
    }

    if total_estimate > state["budget"]:
        over_amount = total_estimate - state["budget"]
        state["budget_status"] = "over"
        state["budget_suggestion"] = generate_budget_suggestion(
            state, over_amount
        )
    elif total_estimate > state["budget"] * 0.9:
        state["budget_status"] = "tight"
        state["budget_suggestion"] = "预算较紧，建议选择性价比更高的住宿"
    else:
        state["budget_status"] = "ok"
        state["budget_suggestion"] = ""

    return state


def generate_budget_suggestion(state, over_amount) -> str:
    # 关键：住宿偏好为"高档型"或"豪华型"时，不建议降级住宿，优先压缩景点
    hotel_locked = state["hotel_level"] in ("高档型", "豪华型")

    prompt = f"""
    旅行预算：{state['budget']}元，当前估算超出：{over_amount}元
    费用明细：{state['estimated_cost']}
    住宿偏好：{state['hotel_level']}（{"用户明确选择高端住宿，不建议降级" if hotel_locked else "可考虑适当降级"}）

    请给出具体的压缩建议，优先级：
    {"1. 减少景点数量（住宿偏好较高，优先保留）" if hotel_locked else "1. 住宿降级（当前：" + str(state['candidate_hotels'][0]['price']) + "元/晚）"}
    {"2. 餐饮降级" if hotel_locked else "2. 减少景点数量"}
    3. 交通方式调整

    输出JSON：
    {{
        "action": "reduce_attractions" | "compress_hotel" | "compress_meals",
        "detail": "具体操作说明",
        "expected_saving": 节省金额
    }}
    """
    return parse_json(llm.invoke(prompt).content)
```

### 5.4 冲突裁决节点

```python
def conflict_resolver_node(state: TravelState) -> TravelState:
    """
    汇聚预算Agent和交通Agent的建议，做出裁决
    """
    has_budget_issue = state["budget_status"] == "over"
    has_route_issue = len(state.get("route_issues", [])) > 0

    if not has_budget_issue and not has_route_issue:
        state["conflict_resolved"] = True
        return state

    # 有冲突，让LLM做综合裁决
    resolve_prompt = f"""
    旅行规划出现以下问题需要协调：

    预算问题：{state.get('budget_suggestion', '无')}
    路线问题：{state.get('route_issues', [])}

    当前方案：
    - 景点：{[a['name'] for a in state['candidate_attractions']]}
    - 住宿：{state['candidate_hotels'][0]['name']} ({state['candidate_hotels'][0]['price']}元/晚)
    - 预算：{state['budget']}元，估算：{state['estimated_cost']['total']}元

    请给出协调后的具体方案：
    {{
        "remove_attractions": ["需要删除的景点名称"],
        "hotel_index": 使用候选酒店列表中的第几个（0开始）,
        "reorder_days": {{1: ["景点名"], 2: ["景点名"]}},
        "resolved": true/false
    }}
    """
    decision = parse_json(llm.invoke(resolve_prompt).content)

    # 执行裁决
    if decision.get("remove_attractions"):
        remove_names = set(decision["remove_attractions"])
        state["candidate_attractions"] = [
            a for a in state["candidate_attractions"]
            if a["name"] not in remove_names
        ]

    if "hotel_index" in decision:
        idx = decision["hotel_index"]
        state["final_hotel"] = state["candidate_hotels"][idx]

    state["conflict_resolved"] = decision.get("resolved", False)
    state["replan_count"] = state.get("replan_count", 0) + 1

    return state
```

---

## 六、高德MCP 数据服务层

### 6.1 架构原则

Agent 不直接调用 MCP，统一通过数据服务层，服务层负责缓存、超时重试、降级。

```python
import asyncio
import hashlib
from functools import lru_cache

class TravelDataService:

    def __init__(self, mcp_client, cache_ttl=3600):
        self.mcp = mcp_client
        self.cache = {}         # 生产环境换成Redis
        self.ttl = cache_ttl
        self.fallback_data = load_fallback_data()  # 本地兜底数据

    async def fetch_attractions(self, city: str, keywords: str, count=20) -> list:
        cache_key = f"attractions:{city}:{keywords}"

        # 1. 查缓存
        if cache_key in self.cache:
            return self.cache[cache_key]

        # 2. 调高德MCP，3秒超时，失败重试1次
        for attempt in range(2):
            try:
                result = await asyncio.wait_for(
                    self.mcp.call("maps_text_search", {
                        "keywords": keywords,
                        "city": city,
                        "types": "风景名胜|旅游景点",
                    }),
                    timeout=5.0
                )
                pois = self._parse_pois(result)
                self.cache[cache_key] = pois    # 写缓存
                return pois

            except (asyncio.TimeoutError, Exception) as e:
                if attempt == 1:
                    # 3. 降级：返回本地热门景点数据
                    print(f"MCP调用失败，降级到本地数据: {e}")
                    return self.fallback_data.get(f"attractions_{city}", [])
                await asyncio.sleep(0.5)

    async def fetch_route(self, origin: dict, destination: dict, mode="walking") -> dict:
        """路径规划，含距离和耗时"""
        try:
            result = await asyncio.wait_for(
                self.mcp.call("maps_direction_walking", {
                    "origin": f"{origin['lng']},{origin['lat']}",
                    "destination": f"{destination['lng']},{destination['lat']}",
                }),
                timeout=5.0
            )
            return self._parse_route(result)
        except Exception:
            # 降级：返回直线距离估算
            distance = self._estimate_distance(origin, destination)
            return {"distance": distance, "duration": int(distance / 4 * 60)}

    def _parse_pois(self, raw_result) -> list:
        """解析高德MCP返回的POI数据为统一格式"""
        pois = []
        for item in raw_result.get("pois", []):
            lng, lat = item.get("location", "0,0").split(",")
            pois.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "address": item.get("address"),
                "location": {"lng": float(lng), "lat": float(lat)},
                "rating": float(item.get("biz_ext", {}).get("rating", 0) or 0),
                "price": float(item.get("biz_ext", {}).get("cost", 0) or 0),
                "open_hours": item.get("biz_ext", {}).get("open_time", ""),
                "tags": item.get("type", "").split(";"),
            })
        return pois
```

### 6.2 本地降级数据结构

```python
# fallback_data.json — 高德MCP不可用时的兜底数据
{
    "attractions_北京": [
        {"name": "故宫", "rating": 4.9, "price": 60, "tags": ["历史", "文化"],
         "location": {"lng": 116.397, "lat": 39.916}},
        {"name": "颐和园", "rating": 4.8, "price": 30, ...},
        {"name": "长城", "rating": 4.9, "price": 40, ...}
    ],
    "attractions_上海": [...],
    "attractions_成都": [...]
}
```

---

## 七、前端展示设计

### 7.1 整体布局（参考携程截图）

```
┌─────────────────────────────────────────────┐
│  左侧：规划进度面板                           │
│                                             │
│  ✅ 了解您的需求                             │
│  ⏳ 搜索景点中... （实时streaming）           │
│     └─ 已找到8个推荐景点                     │
│  ⏳ 筛选住宿中...                            │
│  ○  规划交通路线                             │
│  ○  生成每日行程                             │
│  ○  预算优化                                 │
│                                             │
├─────────────────────────────────────────────┤
│  右侧：实时结果展示                           │
│                                             │
│  [地图组件 - 高德JS API]                     │
│  景点/酒店 Marker 实时出现                   │
│                                             │
│  [行程卡片 - 按天展示]                       │
│  Day 1 ▸  Day 2 ▸  Day 3                   │
│                                             │
│  [费用预算饼图]                              │
└─────────────────────────────────────────────┘
```

### 7.2 流式输出实现

后端通过 SSE（Server-Sent Events）把每个 Agent 的进度实时推送给前端：

```python
# 后端：FastAPI SSE 接口
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

@app.post("/plan")
async def plan_travel(request: TravelRequest):
    async def event_stream():
        # 启动 LangGraph，监听 State 变化
        async for state_update in run_travel_graph(request):
            # 把最新的 streaming_updates 推给前端
            for msg in state_update.get("new_updates", []):
                yield f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n"

            # 如果有新的景点数据，推送给前端渲染地图
            if state_update.get("new_attractions"):
                yield f"data: {json.dumps({'type': 'attractions', 'data': state_update['new_attractions']})}\n\n"

            # 最终行程生成完毕
            if state_update.get("itinerary"):
                yield f"data: {json.dumps({'type': 'itinerary', 'data': state_update['itinerary']})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

```javascript
// 前端：React 接收SSE
useEffect(() => {
  const eventSource = new EventSource('/plan');

  eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);

    if (data.type === 'progress') {
      setProgressSteps(prev => [...prev, data.message]);
    }

    if (data.type === 'attractions') {
      // 实时在高德地图上打点
      addMarkersToMap(data.data);
    }

    if (data.type === 'itinerary') {
      // 渲染最终行程卡片
      setItinerary(data.data);
      eventSource.close();
    }
  };
}, []);
```

### 7.3 前端核心组件清单

```
components/
├── PreferenceSelector.jsx   # 【新增】偏好选择面板（出发地/目的地/日期/同行/风格/节奏/住宿）
├── PlanningProgress.jsx     # 左侧规划进度（Agent执行状态实时更新）
├── MapView.jsx              # 高德地图，含景点/酒店Marker和路线连线
├── ItineraryTabs.jsx        # 按天Tab切换的行程卡片
├── POICard.jsx              # 单个景点/餐厅/酒店卡片（含图片/评分/标签）
├── BudgetChart.jsx          # 预算分配饼图（recharts）
├── WeatherBanner.jsx        # 每日天气展示条
└── BookingLinks.jsx         # 机票/酒店跳转按钮（携程/12306）
```

### 7.4 地图集成（高德 JS API）

```javascript
// MapView.jsx
import AMapLoader from '@amap/amap-jsapi-loader';

const MapView = ({ attractions, hotels, dailyRoutes }) => {
  useEffect(() => {
    AMapLoader.load({ key: 'YOUR_KEY', version: '2.0' }).then(AMap => {
      const map = new AMap.Map('map-container', {
        zoom: 13,
        center: [116.397, 39.916]
      });

      // 景点Marker（橙色）
      attractions.forEach(poi => {
        new AMap.Marker({
          position: [poi.location.lng, poi.location.lat],
          title: poi.name,
          icon: orangeIcon
        }).addTo(map);
      });

      // 每日路线连线（不同天用不同颜色）
      dailyRoutes.forEach((route, dayIndex) => {
        const path = route.pois.map(p => [p.location.lng, p.location.lat]);
        new AMap.Polyline({
          path,
          strokeColor: DAY_COLORS[dayIndex],
          strokeWeight: 3
        }).addTo(map);
      });
    });
  }, [attractions, dailyRoutes]);

  return <div id="map-container" style={{ height: '400px' }} />;
};
```

---

## 八、项目目录结构

```
travel-planner/
├── backend/
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── attraction_agent.py
│   │   ├── restaurant_agent.py
│   │   ├── hotel_agent.py
│   │   ├── weather_agent.py
│   │   ├── budget_agent.py
│   │   ├── transport_agent.py
│   │   ├── conflict_resolver.py
│   │   └── report_agent.py
│   ├── graph/
│   │   ├── state.py              # TravelState定义
│   │   ├── graph_builder.py      # LangGraph图构建
│   │   └── router.py             # 路由函数
│   ├── data_service/
│   │   ├── amap_service.py       # 高德MCP封装（含缓存降级）
│   │   └── fallback_data.json    # 本地降级数据
│   ├── api/
│   │   └── main.py               # FastAPI + SSE接口
│   └── prompts/
│       └── agent_prompts.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── PreferenceSelector.jsx  # 偏好选择面板（产品门面）
│   │   │   ├── PlanningProgress.jsx
│   │   │   ├── MapView.jsx
│   │   │   ├── ItineraryTabs.jsx
│   │   │   ├── POICard.jsx
│   │   │   ├── BudgetChart.jsx
│   │   │   └── WeatherBanner.jsx
│   │   ├── hooks/
│   │   │   └── useTravelPlanning.js  # SSE连接管理
│   │   └── App.jsx
│   └── package.json
│
└── README.md
```

---

## 九、开发顺序

### Phase 1 · 数据服务层（2天）

- 注册高德开放平台，获取 API Key
- 实现 `TravelDataService`，封装景点/餐厅/住宿/天气/路线接口
- 写本地降级数据（北京/上海/成都各10个热门景点）
- 验收：直接调用数据服务，能拿到结构化 POI 数据

### Phase 2 · 单 Agent 跑通（2天）

- 实现景点 Agent，调数据服务 + LLM 筛选
- 不接 LangGraph，直接跑验证效果
- 验收：输入"北京 历史文化"，返回筛选后的景点列表

### Phase 3 · LangGraph 骨架（2-3天）

- 定义 `TravelState`，搭建图结构
- 先实现 Phase 1（4个 Agent 并行），不做约束协调
- 实现报告 Agent，生成简单行程
- 验收：输入需求，能输出一份完整行程

### Phase 4 · 约束协调（3天）

- 实现预算 Agent 和交通 Agent
- 实现冲突裁决节点 + 带环路由
- 测试超预算场景：系统自动压缩方案
- 验收：预算2000游北京3天，系统能自动平衡费用

### Phase 5 · 前端（3-4天）

- 搭建 React 项目，集成高德 JS API
- **优先实现 `PreferenceSelector.jsx`**（产品第一屏，用户最先看到的东西）
- 实现 SSE 连接，进度实时更新
- 实现地图 Marker 实时打点
- 实现行程卡片和预算图表
- 验收：完整体验，效果接近携程截图

---

## 十、简历写法

### 项目标题
```
Multi-Agent 智能旅行规划系统
LangGraph · LangChain · 高德MCP · React · FastAPI
```

### 项目描述
基于 LangGraph 构建的旅行规划 Multi-Agent 系统，采用三阶段架构：结构化表单输入（同行伙伴/风格偏好/行程节奏/住宿档次点选，直接映射 State 无需 LLM 解析）→ 并行数据采集（景点/餐厅/住宿/天气 4 个 Agent Fan-out）→ 约束冲突协调（预算 Agent 与交通 Agent 博弈裁决）→ 行程整合输出。后端通过 SSE 流式推送规划进度，前端实时渲染高德地图 Marker 和行程卡片。

### 核心职责描述

- 设计**结构化偏好表单**替代自然语言输入（同行伙伴/风格偏好/行程节奏/住宿档次四维度点选），表单数据直接映射为 State 字段，Orchestrator 省去 LLM 解析环节，降低意图理解错误率

- 设计**三阶段 Multi-Agent 架构**：并行数据采集（Fan-out）→ 约束冲突协调（预算 Agent 与交通 Agent 互相博弈，Orchestrator 裁决）→ 行程整合，解决旅行规划中时间/预算/路线的多目标平衡问题

- 封装**高德 MCP 数据服务层**，引入本地缓存 + 超时重试 + 本地降级数据三重保障，将 MCP 不稳定性对上层 Agent 的影响降至零

- 基于 LangGraph 实现**带环状态机**，冲突未解决时自动触发重新规划（最多2次），保证系统鲁棒性

- 使用 **FastAPI + SSE** 实现流式输出，每个 Agent 完成后实时推送进度，前端高德地图同步打点，用户体验接近商业产品

- 使用 **Prompt 约束替代框架层工具隔离**，各 Agent 通过 Prompt 明确工具使用边界，实现零框架侵入的工具权限管理

### 面试追问

| 问题 | 回答要点 |
|------|---------|
| 为什么不像携程一样做顺序流程？ | 顺序流程无法处理约束冲突，比如超预算时需要景点Agent和住宿Agent协商取舍，这种多目标平衡是Multi-Agent的核心价值 |
| 高德MCP不稳定怎么处理？ | 数据服务层做缓存+重试+本地降级，Agent只消费结构化数据，MCP是否可用对Agent透明 |
| Agent怎么做工具隔离？ | 没有在框架层做强制隔离，而是在Prompt里明确约束每个Agent只能使用哪些工具，LLM在明确约束下基本不会越界 |
| LangGraph的环怎么防止死循环？ | State里的replan_count计数，超过2次强制走max_retry分支直接输出，图结构层面保证终止 |

---

*技术栈：LangGraph · LangChain · 高德MCP · DeepSeek · FastAPI · React · 高德JS API*
