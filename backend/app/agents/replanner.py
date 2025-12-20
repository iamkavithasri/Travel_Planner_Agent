from typing import List, Dict, Optional
from app.core.schemas import DayPlan, Activity
from app.tools.cost_tool import CostEstimator
import random

class Replanner:
    """Handles re-planning strategies when constraints are violated"""
    
    def __init__(self, cost_estimator: CostEstimator):
        self.cost_estimator = cost_estimator
    
    def reduce_costs(self, days: List[DayPlan], target_reduction: float) -> List[DayPlan]:
        """
        Reduce costs by removing expensive activities
        Strategy: Remove most expensive activities first
        """
        
        # Collect all activities with their day reference
        all_activities = []
        for day in days:
            for activity in day.activities:
                all_activities.append((day.day_number, activity))
        
        # Sort by cost (descending)
        all_activities.sort(key=lambda x: x[1].cost, reverse=True)
        
        # Remove activities until we reach target reduction
        removed_cost = 0
        removed_activities = set()
        
        for day_num, activity in all_activities:
            if removed_cost >= target_reduction:
                break
            
            # Keep at least 1 activity per day
            day_activity_count = sum(
                1 for d, a in all_activities 
                if d == day_num and (d, a.name) not in removed_activities
            )
            
            if day_activity_count > 1:
                removed_activities.add((day_num, activity.name))
                removed_cost += activity.cost
        
        # Rebuild days without removed activities
        new_days = []
        for day in days:
            new_activities = [
                act for act in day.activities 
                if (day.day_number, act.name) not in removed_activities
            ]
            
            if new_activities:  # Only add day if it has activities
                new_day = DayPlan(
                    day_number=day.day_number,
                    activities=new_activities,
                    total_cost=round(sum(act.cost for act in new_activities), 2),
                    total_hours=round(sum(act.duration_hours for act in new_activities), 1)
                )
                new_days.append(new_day)
        
        return new_days
    
    def redistribute_activities(self, days: List[DayPlan], max_hours_per_day: float) -> List[DayPlan]:
        """
        Redistribute activities across days to balance time
        Uses greedy bin-packing algorithm
        """
        
        # Collect all activities
        all_activities = []
        for day in days:
            all_activities.extend(day.activities)
        
        # Sort by duration (longest first for better packing)
        all_activities.sort(key=lambda x: x.duration_hours, reverse=True)
        
        # Create new days
        new_days = [
            DayPlan(
                day_number=i+1, 
                activities=[], 
                total_cost=0, 
                total_hours=0
            ) 
            for i in range(len(days))
        ]
        
        # Distribute activities (greedy algorithm)
        for activity in all_activities:
            # Find day with least hours that can fit this activity
            best_day = None
            min_hours = float('inf')
            
            for day in new_days:
                if day.total_hours + activity.duration_hours <= max_hours_per_day:
                    if day.total_hours < min_hours:
                        min_hours = day.total_hours
                        best_day = day
            
            if best_day:
                best_day.activities.append(activity)
                best_day.total_hours = round(best_day.total_hours + activity.duration_hours, 1)
                best_day.total_cost = round(best_day.total_cost + activity.cost, 2)
        
        # Return only days with activities
        return [day for day in new_days if day.activities]
    
    def replace_expensive_activities(self, days: List[DayPlan], 
                                     available_activities: List[Dict], 
                                     target_reduction: float) -> List[DayPlan]:
        """
        Replace expensive activities with cheaper alternatives
        Maintains activity diversity
        """
        
        # Find expensive activities (top 30% by cost)
        all_activities_with_day = []
        for day in days:
            for activity in day.activities:
                all_activities_with_day.append((day.day_number, activity))
        
        if not all_activities_with_day:
            return days
        
        # Calculate threshold for "expensive"
        costs = [act.cost for _, act in all_activities_with_day]
        costs.sort(reverse=True)
        threshold = costs[max(0, len(costs) // 3)] if costs else 0
        
        expensive_activities = [
            (day_num, act) for day_num, act in all_activities_with_day 
            if act.cost >= threshold and act.cost > 0
        ]
        
        # Sort by cost (most expensive first)
        expensive_activities.sort(key=lambda x: x[1].cost, reverse=True)
        
        # Find cheap alternatives from available activities
        cheap_alternatives = [
            act for act in available_activities 
            if act.get("estimated_cost", 0) < threshold * 0.5
        ]
        
        if not cheap_alternatives:
            # If no cheap alternatives, just reduce costs
            return self.reduce_costs(days, target_reduction)
        
        # Replace expensive activities
        replaced_cost = 0
        replacements = {}
        used_alternatives = set()
        
        for day_num, expensive_act in expensive_activities:
            if replaced_cost >= target_reduction:
                break
            
            # Find unused cheap alternative of similar type
            cheap_act_data = None
            for alt in cheap_alternatives:
                alt_name = alt.get('name', '')
                if alt_name not in used_alternatives:
                    # Prefer similar activity types
                    if expensive_act.type in alt.get('type', '').lower() or \
                       alt.get('type', '').lower() in expensive_act.type:
                        cheap_act_data = alt
                        break
            
            # Fallback to any unused alternative
            if not cheap_act_data:
                for alt in cheap_alternatives:
                    if alt.get('name', '') not in used_alternatives:
                        cheap_act_data = alt
                        break
            
            if cheap_act_data:
                cheap_cost = cheap_act_data.get("estimated_cost", 0)
                cheap_duration = cheap_act_data.get("estimated_duration", 2)
                
                savings = expensive_act.cost - cheap_cost
                if savings > 0:
                    used_alternatives.add(cheap_act_data.get('name', ''))
                    replacements[(day_num, expensive_act.name)] = Activity(
                        name=cheap_act_data.get('name', 'Alternative Activity'),
                        type=cheap_act_data.get('type', 'attraction'),
                        cost=cheap_cost,
                        duration_hours=cheap_duration,
                        time_slot=expensive_act.time_slot,
                        lat=cheap_act_data.get('lat'),
                        lon=cheap_act_data.get('lon'),
                        description=cheap_act_data.get('cuisine') or cheap_act_data.get('opening_hours')
                    )
                    replaced_cost += savings
        
        # Apply replacements
        new_days = []
        for day in days:
            new_activities = []
            for activity in day.activities:
                key = (day.day_number, activity.name)
                if key in replacements:
                    new_activities.append(replacements[key])
                else:
                    new_activities.append(activity)
            
            new_day = DayPlan(
                day_number=day.day_number,
                activities=new_activities,
                total_cost=round(sum(act.cost for act in new_activities), 2),
                total_hours=round(sum(act.duration_hours for act in new_activities), 1)
            )
            new_days.append(new_day)
        
        return new_days