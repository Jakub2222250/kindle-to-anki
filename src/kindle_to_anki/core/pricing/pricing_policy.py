# Reference class

from .cost_estimate import CostEstimate
from .usage_estimate import UsageEstimate


class PricingPolicy:
    def estimate_cost(self, usage: UsageEstimate) -> CostEstimate:
        ...
