"""FastAPI app entrypoint."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, get_logger, setup_logging
from app.ai.mcp.client import initialize_mcp_tools
from app.api.routers import router as api_router

setup_logging()
logger = get_logger("App")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("app startup name=%s version=%s", settings.APP_NAME, settings.APP_VERSION)

    # 初始化 MCP 工具；本地演示可跳过，避免无真实高德 Key 时阻塞应用启动
    if settings.DEMO_MODE:
        logger.warning("demo mode enabled, skip mcp tools initialization")
    elif settings.SKIP_MCP_INIT:
        logger.warning("skip mcp tools initialization")
    else:
        logger.info("initializing mcp tools")
        try:
            await initialize_mcp_tools()
            logger.info("mcp tools initialized")
        except Exception as e:
            logger.error("mcp initialization failed: %s", e)
            raise

    yield

    logger.info("app shutdown")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


# 创建应用实例
app = create_app()
