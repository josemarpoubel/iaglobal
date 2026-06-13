"""Self-critique mechanism for code and output evaluation."""

from typing import Dict, List, Any

class SelfCritique:
    """Evaluates its own outputs and generates critiques."""
    
    def __init__(self):
        self.critique_history = []
        self.improvement_suggestions = []
    
    def critique(self, output: Any, criteria: List[str]) -> Dict:
        """Generate a critique of output based on criteria."""
        critique = {
            'output': output,
            'criteria_evaluated': criteria,
            'strengths': [],
            'weaknesses': [],
            'score': 0.0
        }
        self.critique_history.append(critique)
        return critique
    
    def add_improvement(self, suggestion: str) -> None:
        """Add an improvement suggestion."""
        self.improvement_suggestions.append(suggestion)
    
    def get_critique_summary(self) -> Dict:
        """Get summary of all critiques."""
        return {
            'total_critiques': len(self.critique_history),
            'improvements_suggested': len(self.improvement_suggestions),
            'history': self.critique_history
        }
