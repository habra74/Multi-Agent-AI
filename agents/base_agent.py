import logging
import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)

    def run(self, input_data: dict) -> dict:
        raise NotImplementedError(f"{self.name}.run() must be implemented")

    def _error_output(self, error: str) -> dict:
        self.logger.error(f"{self.name} error: {error}")
        return {
            "agent_name": self.name,
            "summary": f"Analysis failed: {error}",
            "bull_points": [],
            "bear_points": [],
            "confidence": 0.0,
            "evidence": [f"Error: {error}"],
        }
