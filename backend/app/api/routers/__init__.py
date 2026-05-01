"""API 路由模块"""

from fastapi import APIRouter

router = APIRouter()

# 注册旅行规划路由
from app.api.routers.travel import router as travel_router
router.include_router(travel_router, prefix="/travel", tags=["travel"])

# MCP 工具元数据路由
from app.api.routers.mcp import router as mcp_router
router.include_router(mcp_router, prefix="/mcp", tags=["mcp"])

__all__ = ["router"]
