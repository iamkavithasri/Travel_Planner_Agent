import json
from typing import Dict, Optional
import random

class CostEstimator:
    """Dynamic cost estimation based on location and activity type"""
    
    def __init__(self):
        # Base cost multipliers by country tier
        self.country_cost_multipliers = {
            # Tier 1: Very expensive
            "switzerland": 2.5, "norway": 2.3, "iceland": 2.2, "denmark": 2.0,
            "singapore": 1.9, "australia": 1.8, "japan": 1.7, "united kingdom": 1.7,
            "united states": 1.6, "canada": 1.5, "germany": 1.5, "france": 1.4,
            
            # Tier 2: Moderate
            "italy": 1.2, "spain": 1.1, "south korea": 1.1, "united arab emirates": 1.3,
            "portugal": 1.0, "greece": 1.0, "china": 0.9,
            
            # Tier 3: Budget-friendly
            "india": 0.4, "thailand": 0.5, "vietnam": 0.4, "indonesia": 0.45,
            "philippines": 0.4, "egypt": 0.5, "turkey": 0.6, "mexico": 0.6,
            "brazil": 0.7, "argentina": 0.6, "poland": 0.7, "romania": 0.6
        }
        
        # Base activity costs (USD) - will be multiplied by country factor
        self.base_costs = {
            "museum": {"min": 8, "max": 25, "avg": 15},
            "gallery": {"min": 5, "max": 20, "avg": 12},
            "attraction": {"min": 0, "max": 50, "avg": 20},
            "restaurant": {"min": 10, "max": 80, "avg": 30},
            "cafe": {"min": 3, "max": 15, "avg": 8},
            "fast_food": {"min": 5, "max": 15, "avg": 8},
            "park": {"min": 0, "max": 5, "avg": 0},
            "garden": {"min": 0, "max": 10, "avg": 3},
            "beach": {"min": 0, "max": 5, "avg": 0},
            "monument": {"min": 0, "max": 15, "avg": 5},
            "castle": {"min": 10, "max": 30, "avg": 18},
            "tour": {"min": 25, "max": 150, "avg": 60},
            "theme_park": {"min": 40, "max": 120, "avg": 70},
            "entertainment": {"min": 15, "max": 80, "avg": 35},
            "bar": {"min": 10, "max": 50, "avg": 25},
            "nightclub": {"min": 15, "max": 80, "avg": 40},
            "cinema": {"min": 8, "max": 20, "avg": 12},
            "theatre": {"min": 20, "max": 100, "avg": 50},
            "sports_centre": {"min": 10, "max": 40, "avg": 20},
            "viewpoint": {"min": 0, "max": 10, "avg": 2}
        }
        
        # Base durations (hours)
        self.base_durations = {
            "museum": 2.5, "gallery": 2, "attraction": 2, "restaurant": 1.5,
            "cafe": 1, "park": 2, "garden": 1.5, "beach": 3, "monument": 1,
            "castle": 2.5, "tour": 4, "theme_park": 6, "entertainment": 3,
            "bar": 2, "nightclub": 3, "cinema": 2.5, "theatre": 2.5,
            "sports_centre": 2, "viewpoint": 0.5, "fast_food": 0.5
        }
    
    def get_country_multiplier(self, country: Optional[str]) -> float:
        """Get cost multiplier for a country"""
        if not country:
            return 1.0
        
        country_lower = country.lower()
        return self.country_cost_multipliers.get(country_lower, 1.0)
    
    def estimate_activity_cost(self, activity_type: str, country: Optional[str] = None,
                              has_fee: Optional[str] = None) -> float:
        """
        Estimate cost dynamically based on:
        - Activity type
        - Country cost of living
        - Fee information from OSM
        """
        
        # Check if explicitly free
        if has_fee and has_fee.lower() in ["no", "free"]:
            return 0.0
        
        # Normalize activity type
        type_lower = activity_type.lower()
        
        # Find matching cost range
        cost_range = None
        for key in self.base_costs:
            if key in type_lower:
                cost_range = self.base_costs[key]
                break
        
        # Default fallback
        if not cost_range:
            cost_range = self.base_costs["attraction"]
        
        # Calculate base cost with variation
        avg = cost_range["avg"]
        variation = random.uniform(-0.15, 0.15) * avg
        base_cost = avg + variation
        
        # Apply country multiplier
        multiplier = self.get_country_multiplier(country)
        final_cost = base_cost * multiplier
        
        return round(max(0, final_cost), 2)
    
    def estimate_duration(self, activity_type: str) -> float:
        """Estimate duration in hours"""
        type_lower = activity_type.lower()
        
        for key in self.base_durations:
            if key in type_lower:
                return self.base_durations[key]
        
        return 2.0  # Default 2 hours
    
    def calculate_daily_costs(self, num_days: int, country: Optional[str] = None) -> Dict[str, float]:
        """
        Calculate accommodation, food, transport costs
        Dynamically based on country
        """
        multiplier = self.get_country_multiplier(country)
        
        # Base daily costs (USD)
        base_accommodation = 60
        base_food = 30
        base_transport = 10
        
        per_night = base_accommodation * multiplier
        per_day_food = base_food * multiplier
        per_day_transport = base_transport * multiplier
        
        return {
            "accommodation_total": round(per_night * num_days, 2),
            "food_total": round(per_day_food * num_days, 2),
            "transportation_total": round(per_day_transport * num_days, 2),
            "per_night": round(per_night, 2),
            "per_day_food": round(per_day_food, 2),
            "per_day_transport": round(per_day_transport, 2)
        }
    
    def allocate_budget(self, total_budget: float, num_days: int, 
                       country: Optional[str] = None) -> Dict[str, float]:
        """
        Smart budget allocation based on location
        """
        daily_costs = self.calculate_daily_costs(num_days, country)
        
        # Fixed costs
        accommodation = daily_costs["accommodation_total"]
        food = daily_costs["food_total"]
        transportation = daily_costs["transportation_total"]
        
        fixed_total = accommodation + food + transportation
        
        # Remaining for activities
        activities = max(0, total_budget - fixed_total)
        
        return {
            "accommodation": accommodation,
            "food": food,
            "transportation": transportation,
            "activities": activities,
            "fixed_costs": fixed_total,
            "total": total_budget
        }