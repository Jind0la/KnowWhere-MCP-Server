"""
Test script to verify taxonomy validation logic.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engine.memory_processor import MemoryProcessor


async def main():
    processor = MemoryProcessor()
    
    test_cases = [
        # (input_domain, input_category, expected_domain, expected_category_contains)
        (None, None, "KnowWhere", "General"),
        ("Source Code", "Frontend", "KnowWhere", "Source Code / Frontend"),
        ("Testing", "Unit", "KnowWhere", "Testing / Unit"),
        ("RandomDomain", "Something", "KnowWhere", "RandomDomain / Something"),
        ("Personal", "Preferences", "Personal", "Preferences"),
        ("General", "Facts", "General", "Facts"),
        ("knowwhere", "API", "KnowWhere", "API"),  # Casing test
    ]
    
    print("=" * 60)
    print("Taxonomy Validation Test Results")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for input_domain, input_category, expected_domain, expected_category in test_cases:
        result_domain, result_category = processor._validate_and_normalize_taxonomy(
            input_domain, input_category
        )
        
        domain_ok = result_domain == expected_domain
        category_ok = expected_category in result_category if result_category else False
        
        if domain_ok and category_ok:
            print(f"✅ PASS: ({input_domain}, {input_category}) -> ({result_domain}, {result_category})")
            passed += 1
        else:
            print(f"❌ FAIL: ({input_domain}, {input_category})")
            print(f"   Expected: ({expected_domain}, {expected_category})")
            print(f"   Got:      ({result_domain}, {result_category})")
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
