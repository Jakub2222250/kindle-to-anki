#!/usr/bin/env python3
"""
WSD Evaluation Harness - Tests Word Sense Disambiguation across models, runtimes, and prompts.
Results are saved to eval_results/ and summarized to console.
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.prompts import list_prompts
from kindle_to_anki.tasks.wsd.runtime_chat_completion import ChatCompletionWSD
from kindle_to_anki.tasks.wsd.schema import WSDInput

bootstrap_all()

FIXTURES_DIR = Path(__file__).parent / "fixtures"
RESULTS_DIR = Path(__file__).parent / "eval_results"

MODELS = ["gpt-5.1", "gpt-5-mini", "gemini-3-flash-preview"]


@dataclass
class TestCase:
    uid: str
    word: str
    lemma: str
    pos: str
    sentence: str
    source_lang: str
    target_lang: str


@dataclass
class EvalResult:
    uid: str
    word: str
    lemma: str
    sentence: str
    source_lang: str
    target_lang: str
    definition: str
    has_output: bool


@dataclass
class EvalRun:
    timestamp: str
    runtime_id: str
    model_id: str
    prompt_id: Optional[str]
    source_lang: str
    target_lang: str
    total_cases: int
    successful: int
    failed: int
    success_rate: float
    duration_seconds: float
    results: List[EvalResult]


def discover_languages() -> List[str]:
    """Discover available languages from corpus files."""
    languages = []
    for corpus_file in FIXTURES_DIR.glob("wsd_corpus_*.jsonl"):
        lang = corpus_file.stem.replace("wsd_corpus_", "")
        languages.append(lang)
    return sorted(languages)


def load_test_corpus(source_lang: str) -> List[TestCase]:
    """Load test cases from JSONL corpus file for a source language."""
    corpus_path = FIXTURES_DIR / f"wsd_corpus_{source_lang}.jsonl"
    if not corpus_path.exists():
        return []

    cases = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            cases.append(TestCase(**data))
    return cases


def run_evaluation(
    model_id: str,
    source_lang: str,
    target_lang: str,
    prompt_id: Optional[str] = None,
    save_results: bool = True,
    session_dir: Optional[Path] = None,
) -> EvalRun:
    """Run WSD evaluation for a specific configuration."""

    # Load test cases for source language, filter by target language
    all_cases = load_test_corpus(source_lang)
    test_cases = [tc for tc in all_cases if tc.target_lang == target_lang]

    if not test_cases:
        raise ValueError(f"No test cases found for {source_lang} -> {target_lang}")

    # Setup runtime
    runtime = ChatCompletionWSD()
    runtime_config = RuntimeConfig(
        model_id=model_id,
        batch_size=30,
        source_language_code=source_lang,
        target_language_code=target_lang,
        prompt_id=prompt_id,
    )

    # Create inputs
    wsd_inputs = [
        WSDInput(
            uid=tc.uid,
            word=tc.word,
            lemma=tc.lemma,
            pos=tc.pos,
            sentence=tc.sentence
        )
        for tc in test_cases
    ]

    # Run disambiguation
    start_time = time.time()
    wsd_outputs = runtime.disambiguate(
        wsd_inputs,
        runtime_config=runtime_config,
        ignore_cache=False,
        use_test_cache=True,
    )
    duration = time.time() - start_time

    # Evaluate results
    eval_results = []
    successful = 0

    for tc, output in zip(test_cases, wsd_outputs):
        has_output = bool(output.definition and output.definition.strip())
        if has_output:
            successful += 1

        eval_results.append(EvalResult(
            uid=tc.uid,
            word=tc.word,
            lemma=tc.lemma,
            sentence=tc.sentence,
            source_lang=tc.source_lang,
            target_lang=tc.target_lang,
            definition=output.definition,
            has_output=has_output,
        ))

    total = len(test_cases)
    eval_run = EvalRun(
        timestamp=datetime.now().isoformat(),
        runtime_id="chat_completion_wsd",
        model_id=model_id,
        prompt_id=prompt_id,
        source_lang=source_lang,
        target_lang=target_lang,
        total_cases=total,
        successful=successful,
        failed=total - successful,
        success_rate=successful / total if total > 0 else 0,
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
    filename = f"wsd_{eval_run.source_lang}_{eval_run.target_lang}_{eval_run.model_id}{prompt_suffix}.json"

    filepath = output_dir / filename

    data = asdict(eval_run)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Results saved to: {filepath}")


def print_summary(eval_run: EvalRun):
    """Print evaluation summary to console."""
    print("\n" + "=" * 80)
    print("WSD EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Runtime:     {eval_run.runtime_id}")
    print(f"Model:       {eval_run.model_id}")
    print(f"Prompt:      {eval_run.prompt_id or '(default)'}")
    print(f"Languages:   {eval_run.source_lang} -> {eval_run.target_lang}")
    print(f"Duration:    {eval_run.duration_seconds:.2f}s")
    print("-" * 80)
    bar = "█" * int(eval_run.success_rate * 20) + "░" * (20 - int(eval_run.success_rate * 20))
    print(f"SUCCESS:     {eval_run.successful}/{eval_run.total_cases} ({eval_run.success_rate:.1%}) {bar}")
    print("-" * 80)

    # Show all results with definitions
    print("\nRESULTS:")
    for r in eval_run.results:
        status = "✓" if r.has_output else "✗"
        print(f"\n  {status} [{r.uid}] {r.word} ({r.lemma})")
        print(f"    Sentence: \"{r.sentence[:60]}{'...' if len(r.sentence) > 60 else ''}\"")
        print(f"    Definition: {r.definition if r.definition else '(empty)'}")

    print("=" * 80 + "\n")


def run_matrix_evaluation(
    models: List[str],
    source_langs: Optional[List[str]] = None,
    prompt_ids: Optional[List[str]] = None,
):
    """Run evaluation across multiple models, languages, and prompts."""
    prompt_ids = prompt_ids or [None]

    # Discover languages if not specified
    if source_langs is None:
        source_langs = discover_languages()

    # Create session directory for this evaluation run
    session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = RESULTS_DIR / f"session_{session_ts}"
    session_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nResults will be saved to: {session_dir}")

    all_runs = []

    for model_id in models:
        for source_lang in source_langs:
            # Load corpus to find target languages for this source
            test_cases = load_test_corpus(source_lang)
            target_langs = list(set(tc.target_lang for tc in test_cases))

            for target_lang in target_langs:
                for prompt_id in prompt_ids:
                    print(f"\n>>> Evaluating: model={model_id}, {source_lang}->{target_lang}, prompt={prompt_id or 'default'}")
                    try:
                        eval_run = run_evaluation(
                            model_id=model_id,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            prompt_id=prompt_id,
                            session_dir=session_dir,
                        )
                        all_runs.append(eval_run)
                        print_summary(eval_run)
                    except Exception as e:
                        print(f"  ERROR: {e}")

    if len(all_runs) > 1:
        print_comparison_table(all_runs)
        save_comparison_summary(all_runs, session_dir)

    print(f"\nResults saved to: {session_dir}")
    return all_runs


def print_comparison_table(runs: List[EvalRun]):
    """Print comparison table of all runs."""
    print("\n" + "=" * 100)
    print("COMPARISON TABLE")
    print("=" * 100)
    print(f"{'Model':<25} {'Src':<5} {'Tgt':<5} {'Prompt':<15} {'Success':<12} {'Cases':<8} {'Time':<8}")
    print("-" * 100)
    for r in runs:
        prompt = r.prompt_id or "(default)"
        print(f"{r.model_id:<25} {r.source_lang:<5} {r.target_lang:<5} {prompt:<15} "
              f"{r.success_rate:>8.1%}    {r.total_cases:<8} {r.duration_seconds:>6.2f}s")
    print("=" * 100 + "\n")


def save_comparison_summary(runs: List[EvalRun], session_dir: Path):
    """Save comparison summary to session directory."""
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_runs": len(runs),
        "runs": [
            {
                "model_id": r.model_id,
                "source_lang": r.source_lang,
                "target_lang": r.target_lang,
                "prompt_id": r.prompt_id,
                "success_rate": r.success_rate,
                "total_cases": r.total_cases,
                "successful": r.successful,
                "duration_seconds": r.duration_seconds,
            }
            for r in runs
        ],
    }

    filepath = session_dir / "_summary.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Summary saved to: {filepath}")


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
    print("WSD EVALUATION HARNESS - Interactive Mode")
    print("=" * 60)

    # Step 1: Select corpus (source language)
    available_langs = discover_languages()
    if not available_langs:
        print("No corpus files found in fixtures/")
        return

    source_langs = prompt_selection(available_langs, "source language corpus")
    if not source_langs:
        print("Cancelled.")
        return

    # Step 2: Discover and select target languages from selected corpora
    all_target_langs = set()
    for source_lang in source_langs:
        test_cases = load_test_corpus(source_lang)
        for tc in test_cases:
            all_target_langs.add(tc.target_lang)

    target_langs = prompt_selection(sorted(all_target_langs), "target language")
    if not target_langs:
        print("Cancelled.")
        return

    # Step 3: Select models
    selected_models = prompt_selection(MODELS, "models")
    if not selected_models:
        print("Cancelled.")
        return

    # Step 4: Select prompts
    wsd_prompts = list_prompts("wsd")
    all_prompts = ["(default)"] + wsd_prompts
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
    print(f"Source languages: {', '.join(source_langs)}")
    print(f"Target languages: {', '.join(target_langs)}")
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
        for source_lang in source_langs:
            test_cases = load_test_corpus(source_lang)
            corpus_target_langs = set(tc.target_lang for tc in test_cases)

            for target_lang in target_langs:
                if target_lang not in corpus_target_langs:
                    continue

                for prompt_id in selected_prompts:
                    prompt_name = prompt_id or "default"
                    print(f"\n>>> Evaluating: model={model_id}, {source_lang}->{target_lang}, prompt={prompt_name}")
                    try:
                        eval_run = run_evaluation(
                            model_id=model_id,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            prompt_id=prompt_id,
                            session_dir=session_dir,
                        )
                        all_runs.append(eval_run)
                        print_summary(eval_run)
                    except Exception as e:
                        print(f"  ERROR: {e}")

    if len(all_runs) > 1:
        print_comparison_table(all_runs)
        # Save comparison table to session directory
        save_comparison_summary(all_runs, session_dir)

    print(f"\nCompleted {len(all_runs)} evaluation run(s).")
    print(f"Results saved to: {session_dir}")


# === CLI Entry Points ===

def test_single_evaluation():
    """Quick test with default settings."""
    eval_run = run_evaluation(
        model_id="gpt-5.1",
        source_lang="pl",
        target_lang="en",
    )
    print_summary(eval_run)


def test_matrix_evaluation():
    """Run matrix evaluation across multiple configurations."""
    wsd_prompts = list_prompts("wsd")
    print(f"Available WSD prompts: {wsd_prompts}")

    run_matrix_evaluation(
        models=MODELS,
        source_langs=None,  # Auto-discover all languages
        prompt_ids=[None] + wsd_prompts,
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "matrix":
        test_matrix_evaluation()
    else:
        interactive_evaluation()
