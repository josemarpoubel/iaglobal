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
        improvement = {"iteration": self.iterations, "score": score, "result": result}
        self.improvements.append(improvement)

        return improvement
