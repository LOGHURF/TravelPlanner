"""
核心配置管理
使用 pydantic-settings 从环境变量加载配置
"""

import secrets
from pathlib import Path
from typing import Literal, Optional

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录 (backend/)
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    应用程序配置类
    从环境变量加载配置，支持 .env 文件
    """

    model_config = SettingsConfigDict(
        # 使用项目根目录下的 .env 文件
        env_file=str(BASE_DIR / ".env"),
        # 忽略空的环境变量值
        env_ignore_empty=True,
        # 忽略额外的环境变量（不在此类中定义的）
        extra="ignore",
    )

    # ==================== 应用配置 ====================
    # API 版本前缀
    API_V1_STR: str = "/api/v1"

    # 应用名称
    APP_NAME: str = "智能旅行规划系统"

    # 应用版本
    APP_VERSION: str = "2.0.0"

    # 调试模式
    DEBUG: bool = False

    # ==================== 服务器配置 ====================
    # 服务端口
    PORT: int = 8000

    # 前端开发服务器允许的跨域来源，使用逗号分隔
    CORS_ALLOWED_ORIGINS: str = "http://127.0.0.1:5173,http://localhost:5173"

    # ==================== LLM 配置 ====================
    # DeepSeek API Key
    DEEPSEEK_API_KEY: str = ""
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # DeepSeek API Base URL
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"

    # 默认模型
    LLM_MODEL: str = "deepseek-chat"

    # 默认温度
    LLM_TEMPERATURE: float = 1.3

    # ==================== 高德地图配置 ====================
    # 高德地图 API Key
    AMAP_MAPS_API_KEY: str = ""

    # 兼容旧的环境变量名
    AMAP_API_KEY: str = ""

    @computed_field
    @property
    def amap_key(self) -> str:
        """获取高德 API Key（优先使用 AMAP_MAPS_API_KEY）"""
        return self.AMAP_MAPS_API_KEY or self.AMAP_API_KEY

    @computed_field
    @property
    def cors_allowed_origins(self) -> list[str]:
        """解析允许跨域访问后端的前端来源。"""
        return [
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    # ==================== MCP 配置 ====================
    # MCP 服务器 URL
    MCP_AMAP_URL: str = "https://mcp.amap.com/sse"

    # 本地无高德 Key 时可跳过启动期 MCP 初始化，避免开发服务卡在外部工具连接
    SKIP_MCP_INIT: bool = False

    # 无 Key 演示模式：使用内置演示数据跑完整规划链路
    DEMO_MODE: bool = False

    # ==================== 日志配置 ====================
    LOG_LEVEL: str = "INFO"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in {"release", "prod", "production"}:
            return False
        return value


# 创建全局配置对象实例
settings = Settings()
