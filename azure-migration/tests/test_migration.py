#!/usr/bin/env python3
"""
Migration Validation Tests
Compare old system vs new system outputs
"""

import asyncio
import json
import sys
sys.path.insert(0, '..')

# Test queries representing different use cases
TEST_QUERIES = [
    # Andrew's example - the gold standard
    {
        "query": "I'm meeting with a data center operator tomorrow. They're interested in filters for the HVAC system of their high-powered data center. Can you help me?",
        "expected_behavior": "Conversational, asks clarifying questions, recommends MERV 11-15 multi-pleat"
    },
    
    # Part lookup
    {
        "query": "HC9600 price",
        "expected_behavior": "Returns specific product with price and stock"
    },
    
    # Application query
    {
        "query": "brewery filtration 10 micron",
        "expected_behavior": "Recommends 2-3 specific products, mentions yeast/fda"
    },
    
    # Comparison
    {
        "query": "compare HC9600 and CLR130",
        "expected_behavior": "Side-by-side with key difference highlighted"
    },
    
    # Voice-style query
    {
        "query": "Looking for hydraulic filters",
        "expected_behavior": "Narrows to 3, asks about ISO cleanliness"
    },
    
    # Safety escalation
    {
        "query": "hydrogen service at 500 degrees",
        "expected_behavior": "Escalates, no product recommendation"
    }
]

class MigrationTester:
    def __init__(self):
        self.results = []
    
    async def test_query(self, test_case: dict) -> dict:
        """Test a single query against both systems."""
        query = test_case["query"]
        print(f"\n🧪 Testing: {query[:60]}...")
        
        try:
            # Import new unified handler
            from mastermind_v3 import MastermindV3
            import pandas as pd
            
            # Load test data
            df = pd.read_csv("../export.csv")
            
            mastermind = MastermindV3(df)
            
            # Call new system
            result = await mastermind.chat(
                message=query,
                history=[]
            )
            
            # Validate response
            validation = self._validate_response(result, test_case)
            
            return {
                "query": query,
                "response": result["response"][:200],
                "products_count": len(result.get("products", [])),
                "follow_up": result.get("follow_up"),
                "validation": validation,
                "passed": validation["passed"]
            }
            
        except Exception as e:
            return {
                "query": query,
                "error": str(e),
                "passed": False
            }
    
    def _validate_response(self, result: dict, test_case: dict) -> dict:
        """Validate response against expectations."""
        issues = []
        
        # Check 1: No "400 products found"
        response = result.get("response", "")
        if "400" in response and "products" in response:
            issues.append("❌ Says '400 products found'")
        
        # Check 2: Max 3 products
        products = result.get("products", [])
        if len(products) > 5:
            issues.append(f"❌ Returns {len(products)} products (max should be 3)")
        
        # Check 3: Has reasoning
        if result.get("reasoning"):
            issues.append("✅ Shows reasoning")
        
        # Check 4: Conversational (no commands)
        if "say lookup" in response.lower() or "type compare" in response.lower():
            issues.append("❌ Uses command language")
        
        # Check 5: Has follow-up or clear recommendation
        if not result.get("follow_up") and len(products) < 2:
            issues.append("⚠️ No follow-up question")
        
        return {
            "passed": len([i for i in issues if i.startswith("❌")]) == 0,
            "issues": issues
        }
    
    async def run_all_tests(self):
        """Run all test cases."""
        print("=" * 60)
        print("MIGRATION VALIDATION TESTS")
        print("=" * 60)
        
        for test in TEST_QUERIES:
            result = await self.test_query(test)
            self.results.append(result)
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r.get("passed"))
        total = len(self.results)
        
        print(f"\nPassed: {passed}/{total} ({passed/total*100:.0f}%)")
        
        if passed < total:
            print("\nFailed tests:")
            for r in self.results:
                if not r.get("passed"):
                    print(f"  - {r['query'][:50]}...")
                    print(f"    {r.get('validation', {}).get('issues', [])}")
        
        # Save results
        with open("test_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        print("\n📄 Detailed results saved to test_results.json")
        
        return passed == total

if __name__ == "__main__":
    tester = MigrationTester()
    success = asyncio.run(tester.run_all_tests())
    sys.exit(0 if success else 1)
