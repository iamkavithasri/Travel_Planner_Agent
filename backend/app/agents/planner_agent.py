from typing import List, Dict, Optional
from app.core.schemas import (
    TravelInput, Itinerary, DayPlan, Activity, CostBreakdown
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
        self.country = None

    def plan(self, travel_input: TravelInput) -> Dict:
        start_time = time.time()
        self.memory.clear()

        # STEP 1: Fetch activities
        self.memory.log_iteration(
            action="fetch_activities",
            reason=f"Getting activities for {travel_input.city}",
            budget_status={
                "budget": travel_input.budget,
                "spent": 0,
                "remaining": travel_input.budget
            }
        )

        available_activities, country = self.activity_tool.get_activities(
            travel_input.city,
            travel_input.preferences
        )

        self.country = country

        if not available_activities:
            return {
                "success": False,
                "itinerary": None,
                "iterations": self.memory.get_iterations(),
                "message": f"No activities found for {travel_input.city}",
                "planning_time_seconds": round(time.time() - start_time, 2)
            }

        # STEP 2: Budget allocation
        budget_allocation = self.cost_estimator.allocate_budget(
            travel_input.budget,
            travel_input.num_days,
            country
        )

        validator = BudgetValidator(
            travel_input.budget,
            travel_input.num_days
        )
        replanner = Replanner(self.cost_estimator)

        # STEP 3: Initial plan
        self.memory.log_iteration(
            action="generate_initial_plan",
            reason=f"Creating itinerary for {travel_input.city}",
            budget_status=validator.get_budget_status(0)
        )

        current_plan = self._generate_initial_plan(
            travel_input,
            available_activities,
            budget_allocation["activities"]
        )

        iteration = 0

        # STEP 4: Agent loop
        while iteration < settings.MAX_REPLANNING_ITERATIONS:
            iteration += 1

            is_valid, reason, details = validator.validate_plan(current_plan)
            
            #print("\n=== VALIDATION RESULT ===")
            #print("Reason:", reason)
            #print("Details:", details)
            #print("=========================\n")

            if is_valid:
                self.memory.log_iteration(
                    action="plan_validated",
                    reason="All constraints satisfied",
                    budget_status=details
                )
                break

            self.memory.log_iteration(
                action="validation_failed",
                reason=reason,
                budget_status=details
            )

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
                    "planning_time_seconds": round(time.time() - start_time, 2)
                }

        itinerary = self._build_itinerary(
            travel_input,
            current_plan,
            budget_allocation
        )

        return {
            "success": True,
            "itinerary": itinerary,
            "iterations": self.memory.get_iterations(),
            "message": f"Plan created for {travel_input.city}, {country}",
            "planning_time_seconds": round(time.time() - start_time, 2)
        }

    # ------------------------------------------------------------------

    def _generate_initial_plan(
        self,
        travel_input: TravelInput,
        available_activities: List[Dict],
        activity_budget: float
    ) -> List[DayPlan]:

        # Enrich activities
        for act in available_activities:
            act["estimated_cost"] = self.cost_estimator.estimate_activity_cost(
                act["type"],
                self.country,
                act.get("fee")
            )
            act["estimated_duration"] = self.cost_estimator.estimate_duration(
                act["type"]
            )

        # Sort cheapest first
        available_activities.sort(key=lambda x: x["estimated_cost"])

        days: List[DayPlan] = []

        activities_per_day = min(
    6,
    max(2, len(available_activities) // travel_input.num_days)
)
        days_activities = [[] for _ in range(travel_input.num_days)]

        selected = available_activities[:activities_per_day * travel_input.num_days]

        for i, act in enumerate(selected):
                   days_activities[i % travel_input.num_days].append(act)

        
        for day_num in range(travel_input.num_days):
            slice_acts = days_activities[day_num]
            day_activities = []
            day_cost = 0.0
            day_hours = 0.0

            for act in slice_acts:
                day_activities.append(
                    Activity(
                        name=act["name"],
                        type=act["type"],
                        cost=act["estimated_cost"],
                        duration_hours=act["estimated_duration"],
                        time_slot=f"Day {day_num + 1}",
                        lat=act.get("lat"),
                        lon=act.get("lon"),
                        description=act.get("cuisine")
                        or act.get("opening_hours")
                    )
                )
                day_cost += act["estimated_cost"]
                day_hours += act["estimated_duration"]

            days.append(
                DayPlan(
                    day_number=day_num + 1,
                    activities=day_activities,
                    total_cost=round(day_cost, 2),
                    total_hours=round(day_hours, 1)
                )
            )

        return days

    # ------------------------------------------------------------------

    def _replan(
        self,
        current_plan: List[DayPlan],
        issue: str,
        details: Dict,
        replanner: Replanner,
        validator: BudgetValidator,
        available_activities: List[Dict]
    ) -> Optional[List[DayPlan]]:

        if "over budget" in issue.lower():
            target = details.get("overage", 0)
            self.memory.log_iteration(
                action="replan_reduce_costs",
                reason=f"Reducing costs by {target}",
                budget_status=details
            )
            return replanner.reduce_costs(current_plan, target)

        if "too many hours" in issue.lower():
            self.memory.log_iteration(
                action="replan_redistribute",
                reason="Redistributing activities",
                budget_status=details
            )
            return replanner.redistribute_activities(current_plan, 10)

        return None

    # ------------------------------------------------------------------

    def _build_itinerary(
        self,
        travel_input: TravelInput,
        days: List[DayPlan],
        budget_allocation: Dict
    ) -> Itinerary:

        activity_cost = sum(day.total_cost for day in days)

        cost_breakdown = CostBreakdown(
            accommodation=budget_allocation["accommodation"],
            food=budget_allocation["food"],
            transportation=budget_allocation["transportation"],
            activities=activity_cost,
            total=(
                activity_cost
                + budget_allocation["accommodation"]
                + budget_allocation["food"]
                + budget_allocation["transportation"]
            )
        )

        return Itinerary(
            city=travel_input.city,
            days=days,
            total_cost=activity_cost,
            cost_breakdown=cost_breakdown,
            remaining_budget=round(
                travel_input.budget - cost_breakdown.total, 2
            )
        )