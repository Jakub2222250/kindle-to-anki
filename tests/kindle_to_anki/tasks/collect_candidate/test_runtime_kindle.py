#!/usr/bin/env python3
"""
Integration test for Kindle candidate collection runtime.
"""
import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))

from kindle_to_anki.tasks.collect_candidate.runtime_kindle import KindleCandidateRuntime
from kindle_to_anki.tasks.collect_candidate.schema import CandidateInput


def test_collect_candidate_runtime_kindle():
    """Test Kindle candidate collection runtime."""
    
    # Get path to test vocab.db or sample database
    project_root = Path(__file__).parent.parent.parent.parent.parent
    test_db_path = project_root / "data" / "inputs" / "vocab.db"
    
    if not test_db_path.exists():
        print(f"Warning: Test database not found at {test_db_path}")
        print("Skipping candidate collection test - requires vocab.db")
        return
    
    print(f"Testing candidate collection runtime with database: {test_db_path}")
    
    # Create candidate input
    candidate_input = CandidateInput(
        db_path=str(test_db_path),
        last_timestamp=None,  # Full import for test
        incremental=False
    )
    
    # Create runtime
    runtime = KindleCandidateRuntime()
    
    # Test candidate collection
    try:
        outputs = runtime.collect_candidates(candidate_input)
        
        print(f"Candidate collection completed. Got {len(outputs)} candidates.")
        
        if outputs:
            # Show first few examples
            for i, output in enumerate(outputs[:3]):
                print(f"\nCandidate {i+1}:")
                print(f"  Word: {output.word}")
                print(f"  Stem: {output.stem}")
                print(f"  Usage: {output.usage[:100]}..." if len(output.usage) > 100 else f"  Usage: {output.usage}")
                print(f"  Language: {output.language}")
                print(f"  Book: {output.book_title}")
                
                # Basic validation
                assert output.word, f"Empty word for candidate {i+1}"
                assert output.stem, f"Empty stem for candidate {i+1}"
                assert output.usage, f"Empty usage for candidate {i+1}"
                assert output.language, f"Empty language for candidate {i+1}"
        
        print("\n✓ Candidate collection runtime test completed successfully")
        
    except Exception as e:
        print(f"✗ Candidate collection runtime test failed: {e}")
        raise


if __name__ == "__main__":
    test_collect_candidate_runtime_kindle()