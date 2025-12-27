class PlatformRegistry:
    def __init__(self):
        self._platforms = {}

    def register(self, platform):
        self._platforms[platform.id] = platform

    def get(self, platform_id: str):
        return self._platforms[platform_id]

    def list(self):
        return self._platforms.values()
