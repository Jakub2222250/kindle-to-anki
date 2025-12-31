from kindle_to_anki.core.runtimes.runtime_registry import RuntimeRegistry
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.models.registry import ModelRegistry
from kindle_to_anki.core.pricing.token_pricing_policy import TokenPricingPolicy
from kindle_to_anki.platforms.platform_registry import PlatformRegistry
from kindle_to_anki.tasks.tasks import TASKS


def get_options_for_task(task: str, source_language_code: str, target_language_code: str) -> list[dict]:
    """Get available runtime/model options for a specific task."""
    options = []
    for runtime in RuntimeRegistry.list():
        if task not in runtime.supported_tasks:
            continue

        supports_model_families = runtime.supported_model_families
        if not supports_model_families or len(supports_model_families) == 0:
            options.append({
                "task": task,
                "runtime": runtime.id,
                "model_id": None,
                "cost_per_1000": 0.0,
                "available": True
            })
        else:
            models_for_runtime = [
                m for m in ModelRegistry.list()
                if m.family in supports_model_families
            ]
            for model in models_for_runtime:
                runtime_config = RuntimeConfig(
                    model_id=model.id,
                    batch_size=30,
                    source_language_code=source_language_code,
                    target_language_code=target_language_code
                )
                usage_estimate = runtime.estimate_usage(1000, runtime_config)
                token_pricing_policy = TokenPricingPolicy(
                    input_cost_per_1m=model.input_token_cost_per_1m,
                    output_cost_per_1m=model.output_token_cost_per_1m,
                )
                cost = token_pricing_policy.estimate_cost(usage_estimate)
                platform = PlatformRegistry.get(model.platform_id)
                available = platform and platform.validate_credentials()
                options.append({
                    "task": task,
                    "runtime": runtime.id,
                    "model_id": model.id,
                    "cost_per_1000": cost.usd,
                    "available": available
                })
    return options


def show_all_options(source_language_code: str, target_language_code: str):
    """Display all available options for all tasks."""
    for task in TASKS:
        options = get_options_for_task(task, source_language_code, target_language_code)
        for opt in options:
            model_str = opt["model_id"] or "n/a"
            available = "Yes" if opt["available"] else "No"
            print(f"Task: {opt['task']:20s}, Runtime: {opt['runtime']:30s}, Model: {model_str:16s}, Cost/1000: ${opt['cost_per_1000']:.4f}, Available: {available}")


def show_task_options(task: str, source_language_code: str, target_language_code: str) -> list[dict]:
    """Display options for a specific task and return them."""
    options = get_options_for_task(task, source_language_code, target_language_code)
    print(f"\nAvailable options for task '{task}':")
    for i, opt in enumerate(options, 1):
        model_str = opt["model_id"] or "n/a"
        available = "Yes" if opt["available"] else "No"
        print(f"  [{i}] Runtime: {opt['runtime']}, Model: {model_str}, Cost/1000: ${opt['cost_per_1000']:.4f}, Available: {available}")
    return options
