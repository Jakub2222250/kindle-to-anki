class RuntimeRegistry:
    _runtimes: dict[str, object] = {}

    @classmethod
    def register(cls, runtime):
        cls._runtimes[runtime.id] = runtime

    @classmethod
    def get(cls, runtime_id: str):
        return cls._runtimes[runtime_id]

    @classmethod
    def list(cls):
        return cls._runtimes.values()

    @classmethod
    def find_by_task(cls, task: str):
        return [
            runtime for runtime in cls._runtimes.values()
            if task in runtime.supported_tasks
        ]
        
    @classmethod
    def find_by_task_as_dict(cls, task: str):
        return {
            runtime.id: runtime for runtime in cls._runtimes.values()
            if task in runtime.supported_tasks
        }
