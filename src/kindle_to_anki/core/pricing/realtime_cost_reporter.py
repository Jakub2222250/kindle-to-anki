from .usage_breakdown import UsageBreakdown
from .usage_scope import UsageScope
from .usage_dimension import UsageDimension
from .token_pricing_policy import TokenPricingPolicy


class RealtimeCostReporter:
    def __init__(self, model):
        self.model = model
        self.pricing_policy = TokenPricingPolicy(
            input_cost_per_1m=model.input_token_cost_per_1m,
            output_cost_per_1m=model.output_token_cost_per_1m
        )

    def estimate_cost(self, input_tokens: int, estimated_output_tokens: int, item_count: int = 1) -> str:
        usage = UsageBreakdown(
            scope=UsageScope(unit="notes", count=item_count),
            inputs={"tokens": UsageDimension(unit="tokens", quantity=input_tokens)},
            outputs={"tokens": UsageDimension(unit="tokens", quantity=estimated_output_tokens)},
        )
        cost = self.pricing_policy.estimate_cost(usage).usd
        return f"${cost:.6f}" if cost is not None else "unknown"

    def actual_cost(self, input_tokens: int, output_tokens: int, item_count: int = 1) -> str:
        usage = UsageBreakdown(
            scope=UsageScope(unit="notes", count=item_count),
            inputs={"tokens": UsageDimension(unit="tokens", quantity=input_tokens)},
            outputs={"tokens": UsageDimension(unit="tokens", quantity=output_tokens)},
        )
        cost = self.pricing_policy.estimate_cost(usage).usd
        return f"${cost:.6f}" if cost is not None else "unknown"
