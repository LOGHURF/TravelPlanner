"""
Pydantic 数据模型 - 请求/响应模型定义（优化版本）

包含：
- TripRequest: 用户请求（新增偏好字段）
- Agent输出模型: Attraction, Hotel, Restaurant, WeatherInfo
- 行程模型: DailyPlan, TripPlan（增强版本）
"""

from datetime import date, datetime
import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ═══════════════════════════════════════════════════════════
# 请求模型
# ═══════════════════════════════════════════════════════════


class TripRequest(BaseModel):
    """旅行规划请求 - 优化版本

    包含完整的旅行需求信息，用于初始化 LangGraph 状态
    新增：用户偏好字段（直接映射，无需LLM解析）
    """

    model_config = ConfigDict(extra="forbid")

    # 基础信息
    destination: str = Field(
        ..., min_length=2, description="目的地，如'上海'或'北京+周边'"
    )
    start_date: Optional[date] = Field(default=None, description="开始日期（可选）")
    end_date: Optional[date] = Field(default=None, description="结束日期（可选）")
    duration: Optional[int] = Field(default=None, ge=1, le=30, description="出行天数")
    origin: str = Field(default="", description="出发地（可选）")

    # 人数与预算（预算为可选，默认由系统在最终阶段估算）
    num_people: int = Field(default=1, ge=1, description="出行人数")
    budget_per_person: float = Field(default=0, ge=0, description="人均预算（可选，默认不填写）")

    # 用户偏好（新增 - 前端表单直接映射）
    companions: str = Field(
        default="独自",
        description="同行伙伴：独自/家庭/情侣/朋友/老人"
    )
    style_preferences: List[str] = Field(
        default_factory=list,
        description="风格偏好：['文化体验','自然风光','历史古迹','美食','购物']"
    )
    pace: str = Field(
        default="适中",
        description="行程节奏：紧凑/适中/宽松"
    )
    hotel_level: str = Field(
        default="舒适型",
        description="住宿偏好：经济型/舒适型/高档型/豪华型"
    )

    # 其他
    special_requirements: Optional[str] = Field(
        default=None,
        description="特殊要求"
    )

    # MCP 检索透传参数（可选）
    types: str = Field(
        default="",
        description="透传给 maps_text_search 的 types 参数（推荐直接使用该字段）",
    )
    show_fields: str = Field(
        default="",
        description="透传给 maps_text_search 的 show_fields 参数（推荐直接使用该字段）",
    )

    @model_validator(mode="after")
    def validate_trip_window(self) -> "TripRequest":
        if self.start_date and self.end_date:
            derived_days = (self.end_date - self.start_date).days + 1
            if derived_days <= 0:
                raise ValueError("end_date must be on or after start_date")
            if self.duration is not None and self.duration != derived_days:
                raise ValueError("duration must match start_date/end_date")
        return self

    @property
    def days(self) -> int:
        """计算出行天数"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        if self.duration:
            return self.duration
        return 3  # 默认3天

    @property
    def total_budget(self) -> float:
        """计算总预算"""
        return self.budget_per_person * self.num_people

    def to_state_dict(self) -> Dict[str, Any]:
        """转换为 TripState 用的字典"""
        request = self.model_dump()
        request["days"] = self.days
        return {
            "request": request,
            "companions": self.companions,
            "style_preferences": self.style_preferences,
            "pace": self.pace,
            "hotel_level": self.hotel_level
        }


# ═══════════════════════════════════════════════════════════
# Agent 输出模型
# ═══════════════════════════════════════════════════════════


class Location(BaseModel):
    """位置信息"""

    lat: float = Field(..., description="纬度")
    lng: float = Field(..., description="经度")

    def to_str(self) -> str:
        """转换为字符串格式：lng,lat（高德API格式）"""
        return f"{self.lng},{self.lat}"


def _parse_location_value(v: Any) -> dict[str, float] | None:
    if v in (None, "", {}):
        return None
    if isinstance(v, Location):
        return {"lat": v.lat, "lng": v.lng}
    if isinstance(v, dict):
        lat = v.get("lat")
        lng = v.get("lng")
        if lat is None or lng is None:
            return None
        try:
            return {"lat": float(lat), "lng": float(lng)}
        except (TypeError, ValueError):
            return None
    if isinstance(v, str):
        parts = [item.strip() for item in v.split(",")]
        if len(parts) != 2:
            return None
        try:
            lng = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            return None
        return {"lat": lat, "lng": lng}
    return None


class Attraction(BaseModel):
    """景点信息 - 增强版本"""

    # 基础信息
    name: str = Field(..., description="景点名称")
    address: str = Field(default="", description="地址")
    location: Optional[Location] = Field(default=None, description="经纬度")
    description: str = Field(default="", description="景点简介")
    keytag: str = Field(default="", description="高德 POI 关键标签")
    type: str = Field(default="", description="高德 POI 类型")
    photos: List[str] = Field(default_factory=list, description="图片列表")
    tel: str = Field(default="", description="联系电话")

    # 评分与分类
    rating: float = Field(default=0, ge=0, le=5, description="评分（0-5）")
    category: str = Field(default="", description="分类：历史古迹/自然风光/博物馆...")
    tags: List[str] = Field(default_factory=list, description="标签")

    # 游览信息
    visit_duration: str = Field(default="2小时", description="建议游览时长")
    indoor: bool = Field(default=False, description="是否为室内景点")
    best_time: str = Field(default="", description="最佳游览时间")

    # 实用信息（新增）
    ticket_price: float = Field(default=0, description="门票价格（元）")
    open_hours: str = Field(default="", description="开放时间")
    phone: str = Field(default="", description="联系电话")
    open_time2: str = Field(default="", description="高德 biz_ext.opentime2")

    # 图片
    photo: str = Field(default="", description="图片URL")

    @field_validator("location", mode="before")
    def parse_location(cls, v):
        # 兼容 LLM 返回 "lng,lat" 字符串，统一转成内部 Location 结构。
        return _parse_location_value(v)

    @field_validator("photos", mode="before")
    def parse_photos(cls, v):
        # 兼容字符串和高德图片对象数组两种输入。
        if v in (None, "", []):
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if not isinstance(v, list):
            return []

        photos: list[str] = []
        for item in v:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    photos.append(text)
                continue
            if isinstance(item, dict):
                url = str(item.get("url", "") or item.get("photo_url", "") or item.get("photo", "")).strip()
                if url:
                    photos.append(url)
        return photos

    @field_validator("rating", "ticket_price", mode="before")
    def parse_float_fields(cls, v):
        if v in (None, ""):
            return 0
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0

    @model_validator(mode="after")
    def sync_derived_fields(self):
        # 保持原始字段和兼容字段同步，避免下游同时判断多套命名。
        if self.photos and not self.photo:
            self.photo = self.photos[0]
        if self.photo and not self.photos:
            self.photos = [self.photo]

        if self.tel and not self.phone:
            self.phone = self.tel
        if self.phone and not self.tel:
            self.tel = self.phone

        if self.open_time2 and not self.open_hours:
            self.open_hours = self.open_time2
        if self.open_hours and not self.open_time2:
            self.open_time2 = self.open_hours

        if self.type and not self.category:
            self.category = self.type

        if self.keytag and not self.tags:
            parts = [item.strip() for item in re.split(r"[;,|，、]+", self.keytag) if item.strip()]
            self.tags = parts

        return self


class Hotel(BaseModel):
    """酒店信息 - 增强版本"""

    # 基础信息
    name: str = Field(..., description="酒店名称")
    address: str = Field(default="", description="地址")
    location: Optional[Location] = Field(default=None, description="酒店位置")
    description: str = Field(default="", description="酒店简介")
    keytag: str = Field(default="", description="高德 POI 关键标签")
    type: str = Field(default="", description="高德 POI 类型")
    photos: List[str] = Field(default_factory=list, description="图片列表")
    tel: str = Field(default="", description="联系电话")
    open_time2: str = Field(default="", description="高德 biz_ext.opentime2")

    # 评分与档次
    rating: float = Field(default=0, ge=0, le=5, description="评分（0-5）")
    hotel_level: str = Field(default="舒适型", description="酒店级别")
    star_rating: int = Field(default=0, ge=0, le=5, description="星级")

    # 价格（新增）
    price_per_night: float = Field(default=0, description="每晚价格（元）")
    total_price: float = Field(default=0, description="总价格（元）")

    # 位置信息
    distance_to_center: str = Field(default="", description="距市中心距离")
    distance: str = Field(default="", description="距离景点距离")

    # 设施
    amenities: List[str] = Field(default_factory=list, description="设施列表")
    phone: str = Field(default="", description="联系电话")

    # 图片
    photo: str = Field(default="", description="图片URL")
    image_url: str = Field(default="", description="图片URL")

    @field_validator("location", mode="before")
    def parse_location(cls, v):
        # 兼容 "lng,lat" 字符串和字典输入。
        return _parse_location_value(v)

    @field_validator("photos", mode="before")
    def parse_photos(cls, v):
        if v in (None, "", []):
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if not isinstance(v, list):
            return []

        photos: list[str] = []
        for item in v:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    photos.append(text)
                continue
            if isinstance(item, dict):
                url = str(item.get("url", "") or item.get("photo_url", "") or item.get("photo", "")).strip()
                if url:
                    photos.append(url)
        return photos

    @field_validator("rating", "price_per_night", "total_price", mode="before")
    def parse_float_fields(cls, v):
        if v in (None, ""):
            return 0
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0

    @model_validator(mode="after")
    def sync_derived_fields(self):
        if self.photos and not self.photo:
            self.photo = self.photos[0]
        if self.photo and not self.photos:
            self.photos = [self.photo]
        if self.photo and not self.image_url:
            self.image_url = self.photo
        if self.image_url and not self.photo:
            self.photo = self.image_url

        if self.tel and not self.phone:
            self.phone = self.tel
        if self.phone and not self.tel:
            self.tel = self.phone

        return self


class Restaurant(BaseModel):
    """餐厅信息 - 增强版本"""

    # 基础信息
    name: str = Field(..., description="餐饮名称")
    type: str = Field(default="", description="高德 POI 类型")
    meal_type: str = Field(default="lunch", description="餐饮类型：breakfast/lunch/dinner/snack")
    address: Optional[str] = Field(default=None, description="地址")
    location: Optional[Location] = Field(default=None, description="经纬度坐标")
    description: Optional[str] = Field(default=None, description="描述/推荐菜品")
    keytag: str = Field(default="", description="高德 POI 关键标签")
    photos: List[str] = Field(default_factory=list, description="图片列表")
    tel: str = Field(default="", description="联系电话")
    phone: str = Field(default="", description="联系电话")
    open_time2: str = Field(default="", description="高德 biz_ext.opentime2")

    # 评分（新增）
    rating: float = Field(default=0, ge=0, le=5, description="评分（0-5）")

    # 价格
    estimated_cost: int = Field(default=0, description="预估费用(元)")
    price_per_person: int = Field(default=0, description="人均消费(元)")

    # 特色
    cuisine_type: str = Field(default="", description="菜系：川菜/粤菜/本地菜...")
    is_recommended: bool = Field(default=False, description="是否推荐")

    # 图片
    photo: str = Field(default="", description="图片URL")

    @field_validator("location", mode="before")
    def parse_location(cls, v):
        return _parse_location_value(v)

    @field_validator("photos", mode="before")
    def parse_photos(cls, v):
        if v in (None, "", []):
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if not isinstance(v, list):
            return []

        photos: list[str] = []
        for item in v:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    photos.append(text)
                continue
            if isinstance(item, dict):
                url = str(item.get("url", "") or item.get("photo_url", "") or item.get("photo", "")).strip()
                if url:
                    photos.append(url)
        return photos

    @field_validator("rating", mode="before")
    def parse_rating(cls, v):
        if v in (None, ""):
            return 0
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0

    @model_validator(mode="after")
    def sync_derived_fields(self):
        if self.photos and not self.photo:
            self.photo = self.photos[0]
        if self.photo and not self.photos:
            self.photos = [self.photo]

        if self.tel and not self.phone:
            self.phone = self.tel
        if self.phone and not self.tel:
            self.tel = self.phone

        if not self.meal_type:
            self.meal_type = "lunch"

        return self


class WeatherInfo(BaseModel):
    """天气信息 - 增强版本"""

    date: str = Field(..., description="日期")
    day_weather: str = Field(..., description="白天天气")
    night_weather: str = Field(..., description="夜间天气")
    day_temp: int = Field(..., description="白天温度(摄氏度)")
    night_temp: int = Field(..., description="夜间温度(摄氏度)")
    wind_direction: str = Field(..., description="风向")
    wind_power: str = Field(..., description="风力")

    # 新增：出行建议
    suggestion: str = Field(default="", description="出行建议")
    uv_index: str = Field(default="", description="紫外线指数")
    comfort_index: str = Field(default="", description="舒适度指数")

    @field_validator('day_temp', 'night_temp', mode='before')
    def parse_temperature(cls, v):
        """解析温度字符串："16°C" -> 16"""
        if isinstance(v, str):
            v = v.replace('°C', '').replace('℃', '').replace('°', '').strip()
            try:
                return int(v)
            except ValueError:
                return 0
        return v


# ═══════════════════════════════════════════════════════════
# 交通/路线模型（新增）
# ═══════════════════════════════════════════════════════════


class RouteSegment(BaseModel):
    """路线段（两点之间的交通）"""

    from_name: str = Field(..., description="起点名称")
    to_name: str = Field(..., description="终点名称")
    from_location: Location = Field(..., description="起点坐标")
    to_location: Location = Field(..., description="终点坐标")

    # 交通信息
    mode: str = Field(default="driving", description="交通方式：driving/walking/transit")
    distance: float = Field(default=0, description="距离（公里）")
    duration: int = Field(default=0, description="耗时（分钟）")
    cost: float = Field(default=0, description="费用（元）")

    # 详细路线（可选）
    instruction: str = Field(default="", description="路线指引")

    @field_validator("from_location", "to_location", mode="before")
    def parse_location(cls, v):
        parsed = _parse_location_value(v)
        if parsed is None:
            raise ValueError("invalid route location")
        return parsed


class TransportPlan(BaseModel):
    """交通规划"""

    # 大交通（城市间）
    inter_city: Optional[Dict[str, Any]] = Field(
        default=None,
        description="城际交通信息"
    )

    # 市内交通
    daily_routes: List[List[RouteSegment]] = Field(
        default_factory=list,
        description="每日路线列表，每天包含多个路线段"
    )
    daily_plan: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="按天规划后的景点/餐厅/酒店安排"
    )

    # 交通建议
    suggested_mode: str = Field(default="mixed", description="推荐交通方式")
    estimated_transport_cost: float = Field(default=0, description="预估交通费用")
    planning_reason: str = Field(default="", description="多日规划说明")


# ═══════════════════════════════════════════════════════════
# 行程模型
# ═══════════════════════════════════════════════════════════


class DailyPlan(BaseModel):
    """每日行程 - 增强版本"""

    # 基础信息
    date: str = Field(..., description="日期")
    day_index: int = Field(..., description="第几天(从1开始)")
    day_of_week: str = Field(default="", description="星期几")
    description: str = Field(default="", description="当日行程描述/主题")

    # 天气
    weather: Optional[WeatherInfo] = Field(default=None, description="天气概况")
    weather_note: str = Field(default="", description="天气注意事项")

    # 住宿
    accommodation: str = Field(default="", description="住宿安排描述")
    hotel: Optional[Hotel] = Field(default=None, description="酒店信息")
    arrival_transport: Optional[Dict[str, Any]] = Field(
        default=None,
        description="第1天展示的出发地到目的地交通建议",
    )

    # 行程内容
    attractions: List[Attraction] = Field(default_factory=list, description="景点列表")
    meals: List[Restaurant] = Field(default_factory=list, description="餐饮安排")
    route_segments: List[RouteSegment] = Field(default_factory=list, description="路线段")

    # 交通
    transportation: str = Field(default="", description="交通方式")
    transport_mode: str = Field(default="mixed", description="当日主要交通方式")

    # 预算（新增）
    estimated_cost: Dict[str, float] = Field(
        default_factory=dict,
        description="当日预算分解：{'attractions': 100, 'meals': 200, 'transport': 50}"
    )

    # 时间线（新增）
    timeline: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="详细时间安排：[{'time': '09:00', 'activity': '参观故宫', 'type': 'attraction'}]"
    )

    @property
    def total_cost(self) -> float:
        """计算当日总费用"""
        return sum(self.estimated_cost.values())

    @property
    def attraction_count(self) -> int:
        """当日景点数量"""
        return len(self.attractions)


class TripPlan(BaseModel):
    """旅行计划 - 增强版本"""

    # 基础信息
    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    total_days: int = Field(default=0, description="总天数")

    # 每日行程
    days: List[DailyPlan] = Field(default_factory=list, description="每日行程")
    narrative_plan: str = Field(
        default="",
        description="给用户阅读的行程文案（补充卡片展示）",
    )

    # 天气
    weather_info: List[WeatherInfo] = Field(default_factory=list, description="天气信息")
    restaurant_recommendations: List[Restaurant] = Field(
        default_factory=list,
        description="独立餐厅推荐卡片数据",
    )

    # 预算分解（新增）
    budget_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="预算分解：{'hotel': 2000, 'attractions': 500, 'meals': 800, 'transport': 300}"
    )
    total_budget: float = Field(default=0, description="总预算")
    estimated_total_cost: float = Field(default=0, description="预估总费用")
    budget_estimate_range: Dict[str, float] = Field(
        default_factory=dict,
        description="预算区间估算：{'low': 3000, 'high': 4200}"
    )

    # 交通（新增）
    transport: Optional[TransportPlan] = Field(default=None, description="交通规划")

    # 建议与提示
    overall_suggestions: str = Field(default="", description="总体建议")
    packing_tips: List[str] = Field(default_factory=list, description="打包建议")
    important_notes: List[str] = Field(default_factory=list, description="重要提示")

    # 统计信息（新增）
    statistics: Dict[str, Any] = Field(
        default_factory=dict,
        description="统计信息：{'attraction_count': 10, 'restaurant_count': 8}"
    )

    @property
    def total_attractions(self) -> int:
        """总景点数"""
        return sum(day.attraction_count for day in self.days)

    @property
    def budget_status(self) -> str:
        """预算状态"""
        if self.total_budget == 0:
            return "unknown"
        ratio = self.estimated_total_cost / self.total_budget
        if ratio > 1:
            return "over"
        elif ratio > 0.9:
            return "tight"
        return "ok"


# ═══════════════════════════════════════════════════════════
# 兼容旧版模型（保留）
# ═══════════════════════════════════════════════════════════


# 旧版响应模型
class ItineraryResponse(BaseModel):
    """同步接口使用的轻量行程响应"""
    destination: str = ""
    days: int = 0
    hotel: Optional[Dict[str, Any]] = None
    daily_plans: List[DailyPlan] = Field(default_factory=list)
    attraction_count: int = 0
    restaurant_count: int = 0
    narrative_plan: str = ""


class PlanSyncResponse(BaseModel):
    """同步规划返回结构"""
    success: bool = True
    itinerary: Optional[ItineraryResponse] = None
    updates: List[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    version: str = "2.0.0"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
