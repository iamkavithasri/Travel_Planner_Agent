from typing import Dict, List, Tuple
from app.core.schemas import DayPlan

class BudgetValidator:
    """Validates budget and time constraints"""
    
    def __init__(self, total_budget: float, num_days: int):
        self.total_budget = total_budget
        self.num_days = num_days
        self.max_hours_per_day = 10  # Maximum active hours per day
    
    def validate_plan(self, days: List[DayPlan]) -> Tuple[bool, str, Dict]:
        """
        Validate entire plan against constraints
        Returns: (is_valid, reason, details)
        """
        
        # Calculate total cost
        total_cost = sum(day.total_cost for day in days)
        
        # Check budget constraint
        if total_cost > self.total_budget:
            overage = total_cost - self.total_budget
            return False, f"Over budget by ${overage:.2f}", {
                "total_cost": total_cost,
                "budget": self.total_budget,
                "overage": overage,
                "remaining": 0
            }
        
        # Check time constraints
        for day in days:
            if day.total_hours > self.max_hours_per_day:
                return False, f"Day {day.day_number} has too many hours ({day.total_hours}h)", {
                    "day": day.day_number,
                    "hours": day.total_hours,
                    "max_hours": self.max_hours_per_day,
                    "total_cost": total_cost,
                    "budget": self.total_budget
                }
        
        # Check if days match
        if len(days) != self.num_days:
            return False, f"Plan has {len(days)} days but should have {self.num_days}", {
                "planned_days": len(days),
                "required_days": self.num_days,
                "total_cost": total_cost,
                "budget": self.total_budget
            }
        
        # Check if all days have activities
        for day in days:
            if len(day.activities) == 0:
                return False, f"Day {day.day_number} has no activities", {
                    "day": day.day_number,
                    "total_cost": total_cost,
                    "budget": self.total_budget
                }
        
        return True, "Plan is valid", {
            "total_cost": total_cost,
            "budget": self.total_budget,
            "remaining": self.total_budget - total_cost
        }
    
    def check_day_validity(self, day: DayPlan) -> Tuple[bool, str]:
        """Check if a single day is valid"""
        
        if day.total_hours > self.max_hours_per_day:
            return False, f"Too many hours: {day.total_hours}h (max {self.max_hours_per_day}h)"
        
        if len(day.activities) == 0:
            return False, "No activities planned"
        
        return True, "Day is valid"
    
    def get_budget_status(self, current_cost: float) -> Dict[str, float]:
        """Get current budget status"""
        return {
            "total_budget": self.total_budget,
            "spent": current_cost,
            "remaining": self.total_budget - current_cost,
            "utilization_percent": round((current_cost / self.total_budget) * 100, 2)
        }