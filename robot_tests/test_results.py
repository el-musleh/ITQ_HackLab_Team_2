"""
Shared test result reporter.
Call report() after each test to accumulate a clean pass/fail summary.
"""
import time

_results = []
_start_time = None


def reset():
    """Clear all previous results."""
    global _results, _start_time
    _results = []
    _start_time = time.time()


def log(test_name, passed, detail=""):
    """Record one test result."""
    global _results
    _results.append({
        "name": test_name,
        "passed": passed,
        "detail": detail,
    })


def summary():
    """Print a formatted summary of all recorded results."""
    global _results, _start_time
    elapsed = time.time() - (_start_time or time.time())
    passed = sum(1 for r in _results if r["passed"])
    failed = sum(1 for r in _results if not r["passed"])
    total  = len(_results)

    print("=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    print(f"  Total:  {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Time:   {elapsed:.2f}s")
    print("-" * 60)

    for r in _results:
        status = "PASS" if r["passed"] else "FAIL"
        symbol = "[OK]" if r["passed"] else "[XX]"
        print(f"  {symbol} {status:5} — {r['name']}")
        if r["detail"]:
            print(f"         {r['detail']}")

    print("=" * 60)
    if failed > 0:
        print("  ACTION: Fix failed tests before proceeding.")
    else:
        print("  ALL TESTS PASSED — robot is ready.")
    print("=" * 60)

    return {"total": total, "passed": passed, "failed": failed, "results": _results}
