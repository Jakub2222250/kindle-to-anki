class RuntimeRegistry:
    def __init__(self):
        self._runtimes = {}

    def register(self, runtime):
        self._runtimes[runtime.id] = runtime

    def get(self, runtime_id: str):
        return self._runtimes[runtime_id]

    def list(self):
        return self._runtimes.values()
