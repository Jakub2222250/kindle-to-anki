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
    expected: Dict[str, str]


@dataclass
class EvalResult:
    uid: str
    word: str
    sentence: str
    language: str
    expected: Dict[str, str]
    actual: Dict[str, str]
    field_matches: Dict[str, bool]
    overall_match: bool


@dataclass
class EvalRun:
    timestamp: str
    runtime_id: str
    model_id: str
    prompt_id: Optional[str]
    language: str
    total_cases: int
    passed: int
    failed: int
    accuracy: float
    field_accuracy: Dict[str, float]
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
                cases.append(TestCase(**data))
    return cases


def compare_output(expected: Dict[str, str], actual: LUIOutput) -> Dict[str, bool]:
    """Compare expected vs actual output field by field."""
    actual_dict = {
        "lemma": actual.lemma,
        "part_of_speech": actual.part_of_speech,
        "aspect": actual.aspect,
        "original_form": actual.original_form,
        "unit_type": actual.unit_type,
    }
    return {
        field: expected.get(field, "").lower().strip() == actual_dict.get(field, "").lower().strip()
        for field in ["lemma", "part_of_speech", "aspect", "original_form", "unit_type"]
    }


def run_evaluation(
    runtime_id: str = "chat_completion_lui",
    model_id: str = "gpt-4o",
    prompt_id: Optional[str] = None,
    language: str = "pl",
    save_results: bool = True,
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
        ignore_cache=True,  # Always fresh for evaluation
        use_test_cache=False,
    )
    duration = time.time() - start_time

    # Evaluate results
    eval_results = []
    field_correct = {"lemma": 0, "part_of_speech": 0, "aspect": 0, "original_form": 0, "unit_type": 0}
    passed = 0

    for tc, output in zip(test_cases, lui_outputs):
        actual_dict = {
            "lemma": output.lemma,
            "part_of_speech": output.part_of_speech,
            "aspect": output.aspect,
            "original_form": output.original_form,
            "unit_type": output.unit_type,
        }
        field_matches = compare_output(tc.expected, output)
        overall_match = all(field_matches.values())

        if overall_match:
            passed += 1

        for field, matched in field_matches.items():
            if matched:
                field_correct[field] += 1

        eval_results.append(EvalResult(
            uid=tc.uid,
            word=tc.word,
            sentence=tc.sentence,
            language=tc.language,
            expected=tc.expected,
            actual=actual_dict,
            field_matches=field_matches,
            overall_match=overall_match,
        ))

    total = len(test_cases)
    field_accuracy = {field: count / total for field, count in field_correct.items()}

    eval_run = EvalRun(
        timestamp=datetime.now().isoformat(),
        runtime_id=runtime_id,
        model_id=model_id,
        prompt_id=prompt_id,
        language=language,
        total_cases=total,
        passed=passed,
        failed=total - passed,
        accuracy=passed / total,
        field_accuracy=field_accuracy,
        duration_seconds=duration,
        results=eval_results,
    )

    if save_results:
        save_eval_run(eval_run)

    return eval_run


def save_eval_run(eval_run: EvalRun):
    """Save evaluation run to JSON file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Create filename with key identifiers
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prompt_suffix = f"_{eval_run.prompt_id}" if eval_run.prompt_id else ""
    filename = f"lui_{eval_run.language}_{eval_run.model_id}{prompt_suffix}_{ts}.json"

    filepath = RESULTS_DIR / filename

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
    print(f"Duration:  {eval_run.duration_seconds:.2f}s")
    print("-" * 70)
    print(f"OVERALL:   {eval_run.passed}/{eval_run.total_cases} passed ({eval_run.accuracy:.1%})")
    print("-" * 70)
    print("Field Accuracy:")
    for field, acc in eval_run.field_accuracy.items():
        bar = "█" * int(acc * 20) + "░" * (20 - int(acc * 20))
        print(f"  {field:15} {bar} {acc:.1%}")
    print("-" * 70)

    # Show failures
    failures = [r for r in eval_run.results if not r.overall_match]
    if failures:
        print(f"\nFAILED CASES ({len(failures)}):")
        for r in failures:
            print(f"\n  [{r.uid}] {r.word} in: \"{r.sentence}\"")
            for field in ["lemma", "part_of_speech", "aspect", "original_form", "unit_type"]:
                exp = r.expected.get(field, "")
                act = r.actual.get(field, "")
                mark = "✓" if r.field_matches[field] else "✗"
                if not r.field_matches[field]:
                    print(f"    {mark} {field}: expected '{exp}' got '{act}'")
    print("=" * 70 + "\n")


def run_matrix_evaluation(
    models: List[str],
    languages: List[str],
    prompt_ids: Optional[List[str]] = None,
):
    """Run evaluation across multiple models, languages, and prompts."""
    prompt_ids = prompt_ids or [None]  # Default prompt

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
                    )
                    all_runs.append(eval_run)
                    print_summary(eval_run)
                except Exception as e:
                    print(f"  ERROR: {e}")

    # Print comparison table
    if len(all_runs) > 1:
        print_comparison_table(all_runs)

    return all_runs


def print_comparison_table(runs: List[EvalRun]):
    """Print comparison table of all runs."""
    print("\n" + "=" * 90)
    print("COMPARISON TABLE")
    print("=" * 90)
    print(f"{'Model':<20} {'Lang':<6} {'Prompt':<15} {'Accuracy':<10} {'Lemma':<8} {'POS':<8} {'Form':<8}")
    print("-" * 90)
    for r in runs:
        prompt = r.prompt_id or "(default)"
        print(f"{r.model_id:<20} {r.language:<6} {prompt:<15} {r.accuracy:>7.1%}   "
              f"{r.field_accuracy['lemma']:>6.1%}  {r.field_accuracy['part_of_speech']:>6.1%}  "
              f"{r.field_accuracy['original_form']:>6.1%}")
    print("=" * 90 + "\n")


# === CLI Entry Points ===

def test_single_evaluation():
    """Quick test with default settings."""
    eval_run = run_evaluation(
        model_id="gpt-4o",
        language="pl",
    )
    print_summary(eval_run)


def test_matrix_evaluation():
    """Run matrix evaluation across multiple configurations."""
    # Discover available LUI prompts
    lui_prompts = list_prompts("lui")
    print(f"Available LUI prompts: {lui_prompts}")

    run_matrix_evaluation(
        models=["gpt-4o", "gpt-4o-mini"],
        languages=["pl"],
        prompt_ids=[None] + [p for p in lui_prompts if "pl" in p],  # Default + Polish-specific
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "matrix":
        test_matrix_evaluation()
    else:
        test_single_evaluation()
