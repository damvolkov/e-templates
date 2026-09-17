"""python -m e_api: local dev runner (reload on, settings-driven port)."""

import uvicorn

from e_api.main import settings

if __name__ == "__main__":
    uvicorn.run("e_api.main:app", host="127.0.0.1", port=settings.port, reload=True)
