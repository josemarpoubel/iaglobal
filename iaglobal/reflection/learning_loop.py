"""Learning loop for continuous improvement."""

from typing import Callable, Any, Dict

class LearningLoop:
    """Implements a learning loop for continuous improvement."""
    
    def __init__(self):
        self.iterations = 0
        self.scores = []
        self.improvements = []
    
    def iterate(self, agent_func: Callable, task: Any, evaluator: Callable) -> Dict:
        """Run one iteration of the learning loop."""
        self.iterations += 1
        
        # Execute agent
        result = agent_func(task)
        
        # Evaluate result
        score = evaluator(result)
        self.scores.append(score)
        
        # Record improvement
        improvement = {
            'iteration': self.iterations,
            'score': score,
            'result': result
        }
        self.improvements.append(improvement)
        
        return improvement
    
    def get_best_result(self) -> Any:
        """Get the best result so far."""
        if not self.improvements:
            return None
        best = max(self.improvements, key=lambda x: x['score'])
        return best['result']
    
    def get_average_score(self) -> float:
        """Get average score across all iterations."""
        if not self.scores:
            return 0.0
        return sum(self.scores) / len(self.scores)
