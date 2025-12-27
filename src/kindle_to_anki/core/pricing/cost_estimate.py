
class CostEstimate:
    usd: float
    confidence: str

    def __init__(self, usd: float, confidence: str):
        self.usd = usd
        self.confidence = confidence
