from groq import Groq
from app.config import settings
import json

class LLMTool:
    """Groq LLM for intelligent planning decisions"""
    
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.LLM_MODEL
    
    def generate_plan(self, context: dict) -> dict:
        """Generate initial travel plan based on context"""
        
        prompt = f"""You are a travel planning agent. Create a day-by-day itinerary.

Context:
- Budget: ${context['budget']}
- Days: {context['num_days']}
- City: {context['city']}
- Country: {context.get('country', 'Unknown')}
- Preferences: {', '.join(context['preferences'])}
- Available activities: {len(context.get('activities', []))} options
- Activity budget (excluding accommodation/food): ${context.get('activity_budget', 0)}

Activities available:
{self._format_activities(context.get('activities', [])[:20])}

Requirements:
1. Distribute activities across {context['num_days']} days
2. Stay within activity budget of ${context.get('activity_budget', 0)}
3. Match user preferences: {', '.join(context['preferences'])}
4. Plan 6-8 hours of activities per day
5. Balance variety and rest time
6. Prioritize free/cheap activities when possible

Return ONLY a JSON object with this structure:
{{
  "days": [
    {{
      "day_number": 1,
      "activities": ["Activity Name 1", "Activity Name 2", "Activity Name 3"],
      "reasoning": "Brief reason for these choices"
    }}
  ]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean markdown code blocks
            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    if part.strip().startswith("json"):
                        content = part[4:].strip()
                    elif "{" in part and "}" in part:
                        content = part.strip()
            
            return json.loads(content)
            
        except Exception as e:
            print(f"LLM generation error: {e}")
            # Fallback to simple distribution
            return self._simple_fallback_plan(context)
    
    def _format_activities(self, activities: list) -> str:
        """Format activities for LLM prompt"""
        formatted = []
        for act in activities[:15]:  # Limit to avoid token overflow
            formatted.append(
                f"- {act.get('name', 'Unknown')} "
                f"({act.get('type', 'attraction')}, "
                f"${act.get('estimated_cost', 0)}, "
                f"{act.get('estimated_duration', 2)}h)"
            )
        return "\n".join(formatted)
    
    def _simple_fallback_plan(self, context: dict) -> dict:
        """Fallback plan if LLM fails"""
        num_days = context.get('num_days', 3)
        activities = context.get('activities', [])
        
        activities_per_day = max(3, len(activities) // num_days)
        
        days = []
        idx = 0
        for day_num in range(num_days):
            day_activities = []
            for _ in range(min(activities_per_day, len(activities) - idx)):
                if idx < len(activities):
                    day_activities.append(activities[idx]['name'])
                    idx += 1
            
            days.append({
                "day_number": day_num + 1,
                "activities": day_activities,
                "reasoning": "Auto-distributed activities"
            })
        
        return {"days": days}
    
    def suggest_replan(self, context: dict, issue: str) -> dict:
        """Suggest how to fix budget/constraint issues"""
        
        prompt = f"""You are a travel planner fixing a budget issue.

Problem: {issue}

Current situation:
- Budget: ${context['budget']}
- Current cost: ${context['current_cost']}
- Over budget by: ${context['current_cost'] - context['budget']}
- Days: {context['num_days']}
- Country: {context.get('country', 'Unknown')}

Suggest changes to fix this. Return JSON:
{{
  "strategy": "reduce_activities|cheaper_options|redistribute",
  "actions": ["Specific action 1", "Specific action 2"],
  "expected_savings": 100
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            return json.loads(content)
            
        except Exception as e:
            print(f"Replan suggestion error: {e}")
            return {
                "strategy": "reduce_activities",
                "actions": ["Remove most expensive activities"],
                "expected_savings": context['current_cost'] - context['budget']
            }