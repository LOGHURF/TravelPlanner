"""
项目入口
"""

import os
import uvicorn
from app.main import create_app
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")
app = create_app()

if __name__ == "__main__":
    from app.config import settings
    port = int(os.getenv("PORT", str(settings.PORT)))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )