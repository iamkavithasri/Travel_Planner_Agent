from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

class TravelInput(BaseModel):
    budget: float = Field(..., gt=0, description="Total budget in USD")
    num_days: int = Field(..., ge=1, le=30, description="Number of travel days")
    city: str = Field(..., min_length=2, description="Destination city")
    preferences: List[str] = Field(..., min_items=1, description="Activity preferences")

class Activity(BaseModel):
    name: str
    type: str
    cost: float
    duration_hours: float
    time_slot: str
    description: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

class DayPlan(BaseModel):
    day_number: int
    date: Optional[str] = None
    activities: List[Activity]
    total_cost: float
    total_hours: float

class CostBreakdown(BaseModel):
    accommodation: float = 0
    food: float = 0
    activities: float = 0
    transportation: float = 0
    total: float = 0

class Itinerary(BaseModel):
    city: str
    days: List[DayPlan]
    total_cost: float
    cost_breakdown: CostBreakdown
    remaining_budget: float

class IterationLog(BaseModel):
    iteration: int
    timestamp: str
    action: str
    reason: str
    budget_status: Dict[str, float]

class PlanningResponse(BaseModel):
    success: bool
    itinerary: Optional[Itinerary] = None
    iterations: List[IterationLog] = []
    message: str
    planning_time_seconds: float