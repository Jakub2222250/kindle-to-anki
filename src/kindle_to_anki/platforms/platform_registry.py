class PlatformRegistry:
    _platforms: dict[str, object] = {}

    @classmethod
    def register(cls, platform):
        cls._platforms[platform.id] = platform

    @classmethod
    def get(cls, platform_id: str):
        return cls._platforms[platform_id]

    @classmethod
    def list(cls):
        return cls._platforms.values()
