class ModelRegistry:
    _models: dict[str, object] = {}
    
    @classmethod
    def register(cls, model):
        cls._models[model.id] = model

    @classmethod
    def get(cls, model_id: str):
        return cls._models[model_id]
    @classmethod
    def list(cls, family=None):
        return [
            m for m in cls._models.values()
            if family is None or m.family == family
        ]
