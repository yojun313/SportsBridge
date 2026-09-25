import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    dev = os.getenv("ENV", "development") == "development"
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8010")),
        reload=dev,
        reload_dirs=["app"] if dev else None,
        timeout_keep_alive=75,  # 브라우저가 유휴 연결을 재사용할 때 POST가 끊기지 않도록(기본 5초)
    )
