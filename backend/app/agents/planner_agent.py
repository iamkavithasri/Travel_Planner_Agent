from typing import List, Dict, Optional
from app.core.schemas import (
    TravelInput, Itinerary, DayPlan, Activity, 
    CostBreakdown, IterationLog
)
from app.core.memory import PlanningMemory
from app.tools.llm_tool import LLMTool
from app.tools.opentripmap_tool import OpenTripMapTool
from app.tools.cost_tool import CostEstimator
from app.agents.validator import BudgetValidator
from app.agents.replanner import Replanner
from app.config import settings
import time

class PlannerAgent:
    """Main agentic travel planner - works for ANY city worldwide"""
    
    def __init__(self):
        self.llm = LLMTool()
        self.activity_tool = OpenTripMapTool()
        self.cost_estimator = CostEstimator()
        self.memory = PlanningMemory()
        self.country = None  # Will be set during planning
    
    def plan(self, travel_input: TravelInput) -> Dict:
        """
        Main planning method - FULLY GENERIC
        """
        
        start_time = time.time()
        self.memory.clear()
        
        # Step 1: Fetch activities for ANY city
        self.memory.log_iteration(
            action="fetch_activities",
            reason=f"Getting activities for {travel_input.city}",
            budget_status={"budget": travel_input.budget, "spent": 0, "remaining": travel_input.budget}
        )
        
        available_activities, country = self.activity_tool.get_activities(
            travel_input.city, 
            travel_input.preferences
        )
        
        self.country = country  # Store for cost calculations
        
        if not available_activities:
            return {
                "success": False,
                "itinerary": None,
                "iterations": self.memory.get_iterations(),
                "message": f"No activities found for {travel_input.city}. Please check city name.",
                "planning_time_seconds": time.time() - start_time
            }
        
        print(f"Found {len(available_activities)} activities in {travel_input.city}, {country}")
        
        # Step 2: Check if budget is realistic
        budget_allocation = self.cost_estimator.allocate_budget(
            travel_input.budget, 
            travel_input.num_days,
            country
        )
        
        if budget_allocation["activities"] < 20:
            return {
                "success": False,
                "itinerary": None,
                "iterations": self.memory.get_iterations(),
                "message": f"Budget too low for {travel_input.num_days} days in {country}. " +
                          f"Minimum suggested: ${budget_allocation['fixed_costs'] + 50}",
                "planning_time_seconds": time.time() - start_time
            }
        
        # Step 3: Initialize validator and replanner
        validator = BudgetValidator(travel_input.budget, travel_input.num_days)
        replanner = Replanner(self.cost_estimator)
        
        # Step 4: Generate initial plan
        self.memory.log_iteration(
            action="generate_initial_plan",
            reason=f"Creating itinerary for {travel_input.city}",
            budget_status=validator.get_budget_status(0)
        )
        
        initial_plan = self._generate_initial_plan(
            travel_input, 
            available_activities,
            budget_allocation["activities"]
        )
        
        current_plan = initial_plan
        iteration = 0
        
        # Step 5: Agentic loop
        while iteration < settings.MAX_REPLANNING_ITERATIONS:
            iteration += 1
            
            # Validate
            is_valid, reason, details = validator.validate_plan(current_plan)
            
            if is_valid:
                self.memory.log_iteration(
                    action="plan_validated",
                    reason="All constraints satisfied",
                    budget_status=details
                )
                break
            
            # Log failure
            self.memory.log_iteration(
                action="validation_failed",
                reason=reason,
                budget_status=details
            )
            
            # Replan
            current_plan = self._replan(
                current_plan, 
                reason, 
                details, 
                replanner, 
                validator,
                available_activities
            )
            
            if not current_plan:
                return {
                    "success": False,
                    "itinerary": None,
                    "iterations": self.memory.get_iterations(),
                    "message": "Could not create valid plan within constraints",
                    "planning_time_seconds": time.time() - start_time
                }
        
        # Step 6: Build final itinerary
        itinerary = self._build_itinerary(travel_input, current_plan, budget_allocation)
        
        return {
            "success": True,
            "itinerary": itinerary,
            "iterations": self.memory.get_iterations(),
            "message": f"Plan created for {travel_input.city}, {country} in {iteration} iteration(s)",
            "planning_time_seconds": round(time.time() - start_time, 2)
        }
    
    def _generate_initial_plan(self, travel_input: TravelInput, 
                               available_activities: List[Dict],
                               activity_budget: float) -> List[DayPlan]:
        """Generate initial plan with country-aware costs"""
        
        # Enrich activities with costs
        for activity in available_activities:
            activity["estimated_cost"] = self.cost_estimator.estimate_activity_cost(
                activity["type"],
                self.country,
                activity.get("fee")
            )
            activity["estimated_duration"] = self.cost_estimator.estimate_duration(
                activity["type"]
            )
        
        # Sort by cost (prefer free/cheap first)
        available_activities.sort(key=lambda x: x["estimated_cost"])
        
        # Distribute across days
        days = []
        activities_per_day = max(3, len(available_activities) // travel_input.num_days)
        
        idx = 0
        for day_num in range(travel_input.num_days):
            day_activities = []
            day_cost = 0
            day_hours = 0
            
            while idx < len(available_activities) and len(day_activities) < activities_per_day:
                act = available_activities[idx]
                
                # Check constraints
                if day_hours + act["estimated_duration"] <= 10 and \
                   day_cost + act["estimated_cost"] <= activity_budget / travel_input.num_days * 1.5:
                    
                    day_activities.append(Activity(
                        name=act["name"],
                        type=act["type"],
                        cost=act["estimated_cost"],
                        duration_hours=act["estimated_duration"],
                        time_slot=f"Day {day_num + 1}",
                        lat=act.get("lat"),
                        lon=act.get("lon"),
                        description=act.get("cuisine") or act.get("opening_hours")
                    ))
                    
                    day_cost += act["estimated_cost"]
                    day_hours += act["estimated_duration"]
                
                idx += 1
            
            if day_activities:
                days.append(DayPlan(
                    day_number=day_num + 1,
                    activities=day_activities,
                    total_cost=round(day_cost, 2),
                    total_hours=round(day_hours, 1)
                ))
        
        return days
    
    def _replan(self, current_plan: List[DayPlan], issue: str, details: Dict,
                replanner: Replanner, validator: BudgetValidator, 
                available_activities: List[Dict]) -> Optional[List[DayPlan]]:
        """Execute replanning"""
        
        if "over budget" in issue.lower():
            target_reduction = details.get('overage', 0)
            
            self.memory.log_iteration(
                action="replan_reduce_costs",
                reason=f"Reducing costs by ${target_reduction:.2f}",
                budget_status=details
            )
            
            new_plan = replanner.reduce_costs(current_plan, target_reduction)
            
            is_valid, _, new_details = validator.validate_plan(new_plan)
            if not is_valid and "over budget" in _.lower():
                new_plan = replanner.replace_expensive_activities(
                    new_plan, 
                    available_activities, 
                    new_details.get('overage', 0)
                )
            
            return new_plan
        
        elif "too many hours" in issue.lower():
            self.memory.log_iteration(
                action="replan_redistribute",
                reason="Redistributing activities",
                budget_status=validator.get_budget_status(
                    sum(day.total_cost for day in current_plan)
                )
            )
            
            return replanner.redistribute_activities(current_plan, 10)
        
        return None
    
    def _build_itinerary(self, travel_input: TravelInput, 
                        days: List[DayPlan],
                        budget_allocation: Dict) -> Itinerary:
        """Build final itinerary"""
        
        activity_cost = sum(day.total_cost for day in days)
        
        cost_breakdown = CostBreakdown(
            accommodation=budget_allocation['accommodation'],
            food=budget_allocation['food'],
            transportation=budget_allocation['transportation'],
            activities=activity_cost,
            total=activity_cost + budget_allocation['accommodation'] + 
                  budget_allocation['food'] + budget_allocation['transportation']
        )
        
        return Itinerary(
            city=travel_input.city,
            days=days,
            total_cost=activity_cost,
            cost_breakdown=cost_breakdown,
            remaining_budget=round(travel_input.budget - cost_breakdown.total, 2)
        )