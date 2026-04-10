"""Start uvicorn from an explicit path so there's no ambiguity."""
import sys
import os

# Force this directory onto sys.path first
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    dev  = os.environ.get("RENDER") is None          # reload only in local dev
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=dev, reload_dirs=[BASE] if dev else [])
