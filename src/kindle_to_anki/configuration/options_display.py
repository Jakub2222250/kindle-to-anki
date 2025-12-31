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


def show_selected_options(task_settings: dict, source_language_code: str, target_language_code: str, note_count: int):
    """Display the user's selected task settings with estimated costs for the given note count."""
    print(f"\nSelected configuration for {note_count} notes ({source_language_code} -> {target_language_code}):")
    total_cost = 0.0
    for task, setting in task_settings.items():
        runtime_id = setting.get("runtime")
        model_id = setting.get("model_id")
        runtime = RuntimeRegistry.get(runtime_id)
        if not runtime:
            print(f"  {task:15s}: Runtime '{runtime_id}' not found")
            continue
        
        if model_id:
            model = ModelRegistry.get(model_id)
            if model:
                runtime_config = RuntimeConfig(
                    model_id=model_id,
                    batch_size=setting.get("batch_size", 30),
                    source_language_code=source_language_code,
                    target_language_code=target_language_code
                )
                usage = runtime.estimate_usage(note_count, runtime_config)
                pricing = TokenPricingPolicy(
                    input_cost_per_1m=model.input_token_cost_per_1m,
                    output_cost_per_1m=model.output_token_cost_per_1m,
                )
                cost = pricing.estimate_cost(usage).usd
                total_cost += cost
                print(f"  {task:15s}: {runtime_id:30s} | {model_id:16s} | Est: ${cost:.4f}")
            else:
                print(f"  {task:15s}: {runtime_id:30s} | {model_id:16s} | Est: n/a")
        else:
            print(f"  {task:15s}: {runtime_id:30s} | {'n/a':16s} | Est: $0.0000")
    print(f"  {'TOTAL':15s}: {' ':30s}   {' ':16s}   Est: ${total_cost:.4f}")
