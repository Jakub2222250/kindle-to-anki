from kindle_to_anki.core.models.modelspec import ModelSpec


class ModelRegistry:
    _models: dict[str, ModelSpec] = {}
    
    @classmethod
    def register(cls, model: ModelSpec):
        cls._models[model.id] = model

    @classmethod
    def get(cls, model_id: str) -> ModelSpec:
        return cls._models[model_id]
    @classmethod
    def list(cls, family=None) -> list[ModelSpec]:
        return [
            m for m in cls._models.values()
            if family is None or m.family == family
        ]
