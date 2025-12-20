from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.core.schemas import TravelInput, PlanningResponse
from app.agents.planner_agent import PlannerAgent
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Travel Planner Agent API",
    description="Agentic travel planner with budget constraints and replanning - Works for ANY city worldwide",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent
planner = PlannerAgent()

@app.get("/")
def read_root():
    return {
        "message": "Travel Planner Agent API",
        "version": "2.0.0",
        "features": [
            "Works for ANY city worldwide",
            "Dynamic cost estimation by country",
            "Automatic replanning when budget exceeded",
            "Real-time activity data from OpenStreetMap"
        ],
        "status": "running"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "groq_configured": bool(settings.GROQ_API_KEY),
        "osm_enabled": True
    }

@app.post("/plan", response_model=PlanningResponse)
async def create_travel_plan(travel_input: TravelInput):
    """
    Create a travel plan with agentic replanning - Works for ANY city
    
    - **budget**: Total budget in USD (minimum $100)
    - **num_days**: Number of travel days (1-30)
    - **city**: ANY city name (e.g., "Paris", "Mumbai", "Tokyo")
    - **preferences**: Activity preferences (e.g., ["culture", "food", "nature"])
    
    Supported preferences:
    - culture, food, nature, history, shopping, entertainment, 
    - sightseeing, adventure, religious, nightlife
    """
    
    try:
        logger.info(f"Received planning request for {travel_input.city}")
        
        # Validate input
        if travel_input.budget < 100:
            raise HTTPException(
                status_code=400, 
                detail="Budget must be at least $100"
            )
        
        if not travel_input.city.strip():
            raise HTTPException(
                status_code=400,
                detail="City name cannot be empty"
            )
        
        # Create plan
        result = planner.plan(travel_input)
        
        logger.info(
            f"Plan created for {travel_input.city}: "
            f"Success={result['success']}, Time={result['planning_time_seconds']}s"
        )
        
        return PlanningResponse(
            success=result["success"],
            itinerary=result.get("itinerary"),
            iterations=result.get("iterations", []),
            message=result["message"],
            planning_time_seconds=result["planning_time_seconds"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Planning error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Planning failed: {str(e)}"
        )

@app.get("/preferences")
def get_available_preferences():
    """Get list of supported activity preferences"""
    return {
        "preferences": [
            "culture",
            "food",
            "nature",
            "history",
            "shopping",
            "entertainment",
            "sightseeing",
            "adventure",
            "religious",
            "nightlife"
        ],
        "note": "You can use any combination of these preferences"
    }

@app.get("/supported-countries")
def get_supported_countries():
    """Get list of countries with cost data"""
    from app.tools.cost_tool import CostEstimator
    estimator = CostEstimator()
    
    countries = list(estimator.country_cost_multipliers.keys())
    
    return {
        "note": "System works for ALL countries, these have optimized cost data",
        "countries_with_cost_data": countries,
        "total": len(countries)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )