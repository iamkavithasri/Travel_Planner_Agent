from typing import List, Dict
from datetime import datetime
from app.core.schemas import IterationLog

class PlanningMemory:
    """Stores agent's planning iterations and decisions"""
    
    def __init__(self):
        self.iterations: List[IterationLog] = []
        self.current_iteration = 0
    
    def log_iteration(self, action: str, reason: str, budget_status: Dict[str, float]):
        """Log a planning iteration"""
        self.current_iteration += 1
        log = IterationLog(
            iteration=self.current_iteration,
            timestamp=datetime.now().isoformat(),
            action=action,
            reason=reason,
            budget_status=budget_status
        )
        self.iterations.append(log)
        return log
    
    def get_iterations(self) -> List[IterationLog]:
        """Get all logged iterations"""
        return self.iterations
    
    def clear(self):
        """Clear memory for new planning session"""
        self.iterations = []
        self.current_iteration = 0