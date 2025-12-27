
from .usage_breakdown import UsageBreakdown
from .pricing_policy import PricingPolicy
from ..pricing.cost_estimate import CostEstimate

class TokenPricingPolicy(PricingPolicy):
    def __init__(self, input_cost_per_1m, output_cost_per_1m):
        self.input_cost_per_1m = input_cost_per_1m
        self.output_cost_per_1m = output_cost_per_1m

    def estimate_cost(self, usage: UsageBreakdown):
        in_tokens = usage.inputs["tokens"].quantity
        out_tokens = usage.outputs["tokens"].quantity

        usd = (
            in_tokens * self.input_cost_per_1m / 1_000_000 +
            out_tokens * self.output_cost_per_1m / 1_000_000
        )

        return CostEstimate(usd=usd, confidence=usage.confidence)
