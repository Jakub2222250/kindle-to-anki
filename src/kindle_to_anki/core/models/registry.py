class ModelRegistry:
    def __init__(self):
        self._models = {}

    def register(self, model):
        self._models[(model.platform, model.id)] = model

    def get(self, platform: str, model_id: str):
        return self._models[(platform, model_id)]

    def list(self, family=None):
        return [
            m for m in self._models.values()
            if family is None or m.family == family
        ]
