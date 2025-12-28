#!/usr/bin/env python3
"""
Test runner for all integration tests.
Run this script to execute all integration tests for the new tasks architecture.
"""

def run_all_tests():
    """Run all integration tests for the new tasks architecture."""
    
    print("=" * 80)
    print("RUNNING ALL INTEGRATION TESTS - NEW TASKS ARCHITECTURE")
    print("=" * 80)
    print()
    
    test_modules = [
        ('tests.kindle_to_anki.tasks.collect_candidates.test_runtime_kindle', 'Kindle Candidate Collection Runtime'),
        ('tests.kindle_to_anki.tasks.translation.test_runtime_chat_completion', 'Translation Chat Completion Runtime (existing)'),
        ('tests.kindle_to_anki.tasks.translation.test_runtime_llm', 'Translation LLM Runtime'),
        ('tests.kindle_to_anki.tasks.wsd.test_runtime_llm', 'Word Sense Disambiguation LLM Runtime'),
        ('tests.kindle_to_anki.tasks.collocation.test_runtime_llm', 'Collocation Generation LLM Runtime'),
        ('tests.kindle_to_anki.pruning.test_pruning', 'Note Pruning (preserved)')  # Keep pruning as it's not task-based
    ]
    
    passed_tests = 0
    total_tests = len(test_modules)
    
    for module_name, test_name in test_modules:
        print(f"Running {test_name}...")
        try:
            # Import and run the test module
            module = __import__(module_name, fromlist=[''])
            if hasattr(module, 'test_' + module_name.split('.')[-1].replace('test_', '')):
                # Get the test function and run it
                test_func_name = 'test_' + module_name.split('.')[-1].replace('test_', '')
                test_func = getattr(module, test_func_name, None)
                if test_func:
                    test_func()
                else:
                    # Try running the module directly
                    exec(compile(open(module.__file__).read(), module.__file__, 'exec'))
            else:
                # Try running the module directly
                exec(compile(open(module.__file__).read(), module.__file__, 'exec'))
            
            print(f"✓ {test_name} completed")
            passed_tests += 1
        except Exception as e:
            print(f"✗ {test_name} failed: {e}")
        print("-" * 40)
        print()
    
    print("=" * 80)
    print(f"TEST SUMMARY: {passed_tests}/{total_tests} tests passed")
    print("=" * 80)

if __name__ == "__main__":
    run_all_tests()