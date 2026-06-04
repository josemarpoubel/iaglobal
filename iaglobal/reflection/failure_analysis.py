"""Failure analysis for debugging and improvement."""

from typing import Dict, List, Any

class FailureAnalyzer:
    """Analyzes failures to identify root causes and improvement areas."""
    
    def __init__(self):
        self.failure_log = []
    
    def analyze(self, error: Exception, context: Dict) -> Dict:
        """Analyze a failure and extract insights."""
        analysis = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'suggestions': []
        }
        self.failure_log.append(analysis)
        return analysis
    
    def get_patterns(self) -> List[str]:
        """Identify common failure patterns."""
        patterns = {}
        for failure in self.failure_log:
            error_type = failure['error_type']
            patterns[error_type] = patterns.get(error_type, 0) + 1
        return sorted(patterns.keys(), key=lambda x: patterns[x], reverse=True)
    
    def get_suggestions(self, error_type: str) -> List[str]:
        """Get improvement suggestions for an error type."""
        matching = [f for f in self.failure_log if f['error_type'] == error_type]
        all_suggestions = []
        for failure in matching:
            all_suggestions.extend(failure['suggestions'])
        return list(set(all_suggestions))
