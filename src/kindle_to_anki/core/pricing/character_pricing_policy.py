from .usage_breakdown import UsageBreakdown
from .pricing_policy import PricingPolicy
from .cost_estimate import CostEstimate


class CharacterPricingPolicy(PricingPolicy):
    def __init__(self, cost_per_1m_chars: float):
        self.cost_per_1m_chars = cost_per_1m_chars

    def estimate_cost(self, usage: UsageBreakdown):
        chars = usage.inputs["characters"].quantity
        usd = chars * self.cost_per_1m_chars / 1_000_000
        return CostEstimate(usd=usd, confidence=usage.confidence)
