class ModelRegistry:
    _models: dict[tuple[str, str], object] = {}
    
    @classmethod
    def register(cls, model):
        cls._models[(model.platform, model.id)] = model

    @classmethod
    def get(cls, platform: str, model_id: str):
        return cls._models[(platform, model_id)]

    @classmethod
    def list(cls, family=None):
        return [
            m for m in cls._models.values()
            if family is None or m.family == family
        ]
