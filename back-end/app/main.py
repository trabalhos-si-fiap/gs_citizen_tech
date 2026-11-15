from fastapi import FastAPI

from app.api.routes.health import router as health_router

app = FastAPI(
    title="Reclame Já API",
    description="API para registro, encaminhamento e acompanhamento de ocorrências urbanas.",
    version="0.1.0",
)

app.include_router(health_router)


@app.get("/")
def root() -> dict:
    return {"message": "Reclame Já API funcionando"}
