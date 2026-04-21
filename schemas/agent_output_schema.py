from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AgentOutput:
    agent_name: str
    summary: str
    bull_points: List[str] = field(default_factory=list)
    bear_points: List[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "summary": self.summary,
            "bull_points": self.bull_points,
            "bear_points": self.bear_points,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
        }


@dataclass
class DecisionOutput(AgentOutput):
    final_decision: str = "HOLD"
    reasoning: str = ""

    def to_dict(self) -> dict:
        base = super().to_dict()
        base["final_decision"] = self.final_decision
        base["reasoning"] = self.reasoning
        return base
