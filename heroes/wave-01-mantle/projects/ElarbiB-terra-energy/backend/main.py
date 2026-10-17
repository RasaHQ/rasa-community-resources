from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import nasa_power, analysis, llm, geospatial, equipment, map as map_router, weather

app = FastAPI(
    title="Intelligent Renewable Energy Assessment Platform",
    description="AI-powered solar and wind energy analysis using NASA POWER data and Mistral LLM",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(nasa_power.router)
app.include_router(analysis.router)
app.include_router(llm.router)
app.include_router(geospatial.router)
app.include_router(equipment.router)
app.include_router(map_router.router)
app.include_router(weather.router)


@app.get("/")
async def root():
    return {
        "name": "Intelligent Renewable Energy Assessment Platform",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
