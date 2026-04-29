from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routes.analyze import router as analyze_router
from app.routes.chat import router as chat_router
from app.routes.fraud import router as fraud_router
from app.routes.financial_score import router as financial_score_router
from app.routes.health import router as health_router
from app.routes.preferences import router as preferences_router
from app.routes.simulation import router as simulation_router
from app.routes.transactions import router as transactions_router

settings = get_settings()

# Support a single URL or comma-separated list in FRONTEND_URL.
configured_origins = [origin.strip().rstrip("/") for origin in settings.frontend_url.split(",") if origin.strip()]
default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
allow_origins = sorted(set(configured_origins + default_origins))

app = FastAPI(
    title="CareBank API",
    description="AI-powered financial wellness system with multi-agent analysis.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router)
app.include_router(chat_router)
app.include_router(fraud_router)
app.include_router(financial_score_router)
app.include_router(health_router)
app.include_router(preferences_router)
app.include_router(simulation_router)
app.include_router(transactions_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "CareBank API is running."}
