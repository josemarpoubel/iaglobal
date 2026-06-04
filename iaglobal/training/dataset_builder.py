"""Dataset builder for training data collection and management."""

from typing import List, Dict, Any

class DatasetBuilder:
    """Builds training datasets from execution results."""
    
    def __init__(self):
        self.samples = []
        self.metadata = {}
    
    def add_sample(self, input_data: Any, output_data: Any, metadata: Dict = None) -> None:
        """Add a training sample to the dataset."""
        sample = {
            'input': input_data,
            'output': output_data,
            'metadata': metadata or {}
        }
        self.samples.append(sample)
    
    def build(self) -> List[Dict]:
        """Build and return the complete dataset."""
        return self.samples
    
    def save(self, filepath: str) -> None:
        """Save dataset to file."""
        import json
        with open(filepath, 'w') as f:
            json.dump(self.samples, f, indent=2)
    
    def load(self, filepath: str) -> None:
        """Load dataset from file."""
        import json
        with open(filepath, 'r') as f:
            self.samples = json.load(f)
