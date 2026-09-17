"""e-api entrypoint: FastAPI app wired to typed settings and structured logging."""

from fastapi import FastAPI

from e_api.core.logger import setup
from e_api.core.settings import BaseSettings


##### CONFIG #####
class Settings(BaseSettings, frozen=True):
    env: str = "dev"
    port: int = 8000


settings = Settings.load()
setup(env=settings.env)

##### APP #####
app = FastAPI(title="e-api")


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
