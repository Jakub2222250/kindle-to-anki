#!/usr/bin/env python3
"""
LUI Evaluation Harness - Tests Lexical Unit Identification across models, runtimes, and prompts.
Results are saved to eval_results/ (gitignored) and summarized to console.
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.prompts import list_prompts
from kindle_to_anki.core.models.registry import ModelRegistry
from kindle_to_anki.tasks.lui.runtime_chat_completion import ChatCompletionLUI
from kindle_to_anki.tasks.lui.schema import LUIInput, LUIOutput

bootstrap_all()

FIXTURES_DIR = Path(__file__).parent / "fixtures"
RESULTS_DIR = Path(__file__).parent / "eval_results"


@dataclass
class TestCase:
    uid: str
    word: str
    sentence: str
    language: str


@dataclass
class EvalResult:
    uid: str
    word: str
    sentence: str
    language: str
    actual: Dict[str, str]


@dataclass
class EvalRun:
    timestamp: str
    runtime_id: str
    model_id: str
    prompt_id: Optional[str]
    language: str
    total_cases: int
    duration_seconds: float
    results: List[EvalResult]


def load_test_corpus(language: Optional[str] = None) -> List[TestCase]:
    """Load test cases from JSONL corpus file."""
    corpus_path = FIXTURES_DIR / "lui_test_corpus.jsonl"
    cases = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if language is None or data["language"] == language:
                cases.append(TestCase(
                    uid=data["uid"],
                    word=data["word"],
                    sentence=data["sentence"],
                    language=data["language"],
                ))
    return cases


def run_evaluation(
    runtime_id: str = "chat_completion_lui",
    model_id: str = "gpt-4o",
    prompt_id: Optional[str] = None,
    language: str = "pl",
    save_results: bool = True,
    session_dir: Optional[Path] = None,
) -> EvalRun:
    """Run evaluation for a specific configuration."""

    # Load test cases for language
    test_cases = load_test_corpus(language)
    if not test_cases:
        raise ValueError(f"No test cases found for language: {language}")

    # Setup runtime
    runtime = ChatCompletionLUI()
    runtime_config = RuntimeConfig(
        model_id=model_id,
        batch_size=30,
        source_language_code=language,
        target_language_code="en",
        prompt_id=prompt_id,
    )

    # Create inputs
    lui_inputs = [
        LUIInput(uid=tc.uid, word=tc.word, sentence=tc.sentence)
        for tc in test_cases
    ]

    # Run identification
    start_time = time.time()
    lui_outputs = runtime.identify(
        lui_inputs,
        runtime_config=runtime_config,
        ignore_cache=False,
        use_test_cache=True,
    )
    duration = time.time() - start_time

    # Collect results
    eval_results = []
    for tc, output in zip(test_cases, lui_outputs):
        actual_dict = {
            "lemma": output.lemma,
            "part_of_speech": output.part_of_speech,
            "aspect": output.aspect,
            "surface_lexical_unit": output.surface_lexical_unit,
            "unit_type": output.unit_type,
        }
        eval_results.append(EvalResult(
            uid=tc.uid,
            word=tc.word,
            sentence=tc.sentence,
            language=tc.language,
            actual=actual_dict,
        ))

    eval_run = EvalRun(
        timestamp=datetime.now().isoformat(),
        runtime_id=runtime_id,
        model_id=model_id,
        prompt_id=prompt_id,
        language=language,
        total_cases=len(test_cases),
        duration_seconds=duration,
        results=eval_results,
    )

    if save_results:
        save_eval_run(eval_run, session_dir)

    return eval_run


def save_eval_run(eval_run: EvalRun, session_dir: Optional[Path] = None):
    """Save evaluation run to JSON file."""
    output_dir = session_dir if session_dir else RESULTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_suffix = f"_{eval_run.prompt_id}" if eval_run.prompt_id else ""
    filename = f"lui_{eval_run.language}_{eval_run.model_id}{prompt_suffix}.json"

    filepath = output_dir / filename

    # Convert to serializable dict
    data = asdict(eval_run)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Results saved to: {filepath}")


def print_summary(eval_run: EvalRun):
    """Print evaluation summary to console."""
    print("\n" + "=" * 70)
    print("LUI EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Runtime:   {eval_run.runtime_id}")
    print(f"Model:     {eval_run.model_id}")
    print(f"Prompt:    {eval_run.prompt_id or '(default)'}")
    print(f"Language:  {eval_run.language}")
    print(f"Cases:     {eval_run.total_cases}")
    print(f"Duration:  {eval_run.duration_seconds:.2f}s")
    print("-" * 70)

    # Show all results
    print("\nRESULTS:")
    for r in eval_run.results:
        print(f"\n  [{r.uid}] {r.word}")
        print(f"    Sentence: \"{r.sentence[:80]}{'...' if len(r.sentence) > 80 else ''}\"")
        print(f"    Lemma: {r.actual.get('lemma', '')}")
        print(f"    POS: {r.actual.get('part_of_speech', '')}")
        print(f"    Aspect: {r.actual.get('aspect', '')}")
        print(f"    Form: {r.actual.get('surface_lexical_unit', '')}")
        print(f"    Type: {r.actual.get('unit_type', '')}")
    print("=" * 70 + "\n")


def run_matrix_evaluation(
    models: List[str],
    languages: List[str],
    prompt_ids: Optional[List[str]] = None,
):
    """Run evaluation across multiple models, languages, and prompts."""
    prompt_ids = prompt_ids or [None]  # Default prompt

    # Create session directory for this evaluation run
    session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = RESULTS_DIR / f"session_{session_ts}"
    session_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nResults will be saved to: {session_dir}")

    all_runs = []

    for model_id in models:
        for language in languages:
            for prompt_id in prompt_ids:
                print(f"\n>>> Evaluating: model={model_id}, lang={language}, prompt={prompt_id or 'default'}")
                try:
                    eval_run = run_evaluation(
                        model_id=model_id,
                        language=language,
                        prompt_id=prompt_id,
                        session_dir=session_dir,
                    )
                    all_runs.append(eval_run)
                    print_summary(eval_run)
                except Exception as e:
                    print(f"  ERROR: {e}")

    # Print comparison table
    if len(all_runs) > 1:
        print_comparison_table(all_runs)
        print_side_by_side_comparison(all_runs)
        save_comparison_summary(all_runs, session_dir)

    print(f"\nResults saved to: {session_dir}")
    return all_runs


def print_comparison_table(runs: List[EvalRun]):
    """Print comparison table of all runs."""
    print("\n" + "=" * 70)
    print("COMPARISON TABLE")
    print("=" * 70)
    print(f"{'Model':<25} {'Lang':<6} {'Prompt':<20} {'Cases':<8} {'Time':<8}")
    print("-" * 70)
    for r in runs:
        prompt = r.prompt_id or "(default)"
        print(f"{r.model_id:<25} {r.language:<6} {prompt:<20} {r.total_cases:<8} {r.duration_seconds:>6.2f}s")
    print("=" * 70 + "\n")


def print_side_by_side_comparison(runs: List[EvalRun]):
    """Print side-by-side comparison of results for each input across all configurations."""
    if not runs:
        return

    # Group runs by language to compare same inputs
    from collections import defaultdict
    runs_by_lang = defaultdict(list)
    for run in runs:
        runs_by_lang[run.language].append(run)

    print("\n" + "=" * 140)
    print("SIDE-BY-SIDE COMPARISON (by input)")
    print("=" * 140)

    for language, lang_runs in runs_by_lang.items():
        if len(lang_runs) < 2:
            continue

        print(f"\n{'─' * 140}")
        print(f"  Language: {language}")
        print(f"{'─' * 140}")

        # Get all UIDs from first run (assuming same inputs across runs)
        first_run = lang_runs[0]
        results_by_uid = {r.uid: {} for r in first_run.results}

        for run in lang_runs:
            label = f"{run.model_id}|{run.prompt_id or 'default'}"
            for r in run.results:
                if r.uid in results_by_uid:
                    results_by_uid[r.uid][label] = r

        # Print each input with all its results
        for result in first_run.results:
            uid = result.uid
            print(f"\n  ┌─ {result.word} [{uid}]")
            print(f"  │  \"{result.sentence[:100]}{'...' if len(result.sentence) > 100 else ''}\"")
            print(f"  │")

            for run in lang_runs:
                label = f"{run.model_id}|{run.prompt_id or 'default'}"
                r = results_by_uid[uid].get(label)
                if r:
                    model_short = run.model_id[:20]
                    prompt_short = run.prompt_id or "default"
                    config_label = f"{model_short}, {prompt_short}"
                    actual = r.actual
                    print(f"  │  ({config_label:30}): lemma={actual.get('lemma', '')[:20]} | pos={actual.get('part_of_speech', '')} | form={actual.get('surface_lexical_unit', '')[:25]}")

            print(f"  └{'─' * 120}")

    print("\n" + "=" * 140 + "\n")


def save_comparison_summary(runs: List[EvalRun], session_dir: Path):
    """Save comparison summary to session directory."""
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_runs": len(runs),
        "runs": [
            {
                "model_id": r.model_id,
                "language": r.language,
                "prompt_id": r.prompt_id,
                "total_cases": r.total_cases,
                "duration_seconds": r.duration_seconds,
            }
            for r in runs
        ],
    }

    filepath = session_dir / "_summary.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Summary saved to: {filepath}")


def discover_languages() -> List[str]:
    """Discover available languages from corpus file."""
    corpus_path = FIXTURES_DIR / "lui_test_corpus.jsonl"
    if not corpus_path.exists():
        return []

    languages = set()
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            languages.add(data["language"])
    return sorted(languages)


def prompt_selection(items: List[str], item_type: str, allow_all: bool = True) -> List[str]:
    """Interactive selection of items from a list."""
    print(f"\n{'=' * 60}")
    print(f"Available {item_type}:")
    print(f"{'=' * 60}")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item}")
    if allow_all:
        print(f"  a. All")
    print(f"  q. Quit")

    while True:
        choice = input(f"\nSelect {item_type} (comma-separated numbers, 'a' for all, 'q' to quit): ").strip().lower()
        if choice == 'q':
            return []
        if choice == 'a' and allow_all:
            return items
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(',')]
            selected = [items[i] for i in indices if 0 <= i < len(items)]
            if selected:
                return selected
            print("Invalid selection, try again.")
        except (ValueError, IndexError):
            print("Invalid input, try again.")


def interactive_evaluation():
    """Run evaluation with interactive configuration selection."""
    print("\n" + "=" * 60)
    print("LUI EVALUATION HARNESS - Interactive Mode")
    print("=" * 60)

    # Step 1: Select language
    available_langs = discover_languages()
    if not available_langs:
        print("No corpus files found in fixtures/")
        return

    languages = prompt_selection(available_langs, "languages")
    if not languages:
        print("Cancelled.")
        return

    # Step 2: Select models
    models = ModelRegistry.list(family="chat_completion")
    model_ids = [m.id for m in models]
    selected_models = prompt_selection(model_ids, "models")
    if not selected_models:
        print("Cancelled.")
        return

    # Step 3: Select prompts
    lui_prompts = list_prompts("lui")
    all_prompts = ["(default)"] + lui_prompts
    selected_prompt_names = prompt_selection(all_prompts, "prompts")
    if not selected_prompt_names:
        print("Cancelled.")
        return

    # Convert "(default)" back to None
    selected_prompts = [None if p == "(default)" else p for p in selected_prompt_names]

    # Confirm selection
    print("\n" + "=" * 60)
    print("CONFIGURATION SUMMARY")
    print("=" * 60)
    print(f"Languages: {', '.join(languages)}")
    print(f"Models: {', '.join(selected_models)}")
    print(f"Prompts: {', '.join(selected_prompt_names)}")

    confirm = input("\nProceed with evaluation? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    # Create session directory for this evaluation run
    session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = RESULTS_DIR / f"session_{session_ts}"
    session_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nResults will be saved to: {session_dir}")

    # Run evaluations
    all_runs = []
    for model_id in selected_models:
        for language in languages:
            for prompt_id in selected_prompts:
                prompt_name = prompt_id or "default"
                print(f"\n>>> Evaluating: model={model_id}, lang={language}, prompt={prompt_name}")
                try:
                    eval_run = run_evaluation(
                        model_id=model_id,
                        language=language,
                        prompt_id=prompt_id,
                        session_dir=session_dir,
                    )
                    all_runs.append(eval_run)
                    print_summary(eval_run)
                except Exception as e:
                    print(f"  ERROR: {e}")

    if len(all_runs) > 1:
        print_comparison_table(all_runs)
        print_side_by_side_comparison(all_runs)
        save_comparison_summary(all_runs, session_dir)

    print(f"\nCompleted {len(all_runs)} evaluation run(s).")
    print(f"Results saved to: {session_dir}")


# === CLI Entry Points ===

def test_single_evaluation():
    """Quick test with default settings."""
    models = ModelRegistry.list(family="chat_completion")
    model_id = models[0].id if models else "gemini-2.5-flash"
    eval_run = run_evaluation(
        model_id=model_id,
        language="pl",
    )
    print_summary(eval_run)


def test_matrix_evaluation():
    """Run matrix evaluation across multiple configurations."""
    # Discover available LUI prompts
    lui_prompts = list_prompts("lui")
    print(f"Available LUI prompts: {lui_prompts}")

    # Get models from registry
    models = ModelRegistry.list(family="chat_completion")
    model_ids = [m.id for m in models]
    print(f"Available models: {model_ids}")

    run_matrix_evaluation(
        models=model_ids,
        languages=["pl"],
        prompt_ids=[None] + [p for p in lui_prompts if "pl" in p],  # Default + Polish-specific
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "matrix":
        test_matrix_evaluation()
    else:
        interactive_evaluation()
