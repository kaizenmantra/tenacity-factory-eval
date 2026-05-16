"""Operator-owned acceptance test for tenacity issue #544.

Exits 0 if the fix correctly surfaces the underlying exception (from
__context__) when TryAgain is raised inside an `except` block and
the retrying iterator is configured with reraise=True. The check is
intentionally black-box: it does not constrain HOW the fix is
implemented, only the externally observable behavior.

Tests three things:
  1. SYNC: Retrying + reraise=True + TryAgain raised from `except`
     bubbles the underlying exception, not TryAgain.
  2. ASYNC: AsyncRetrying + reraise=True + TryAgain raised from
     `except` bubbles the underlying exception, not TryAgain.
  3. Regression guard: an ordinary success-on-retry scenario still
     works (no spurious exception introduced by the fix).

This file is NOT in the contract's allowed_files; the worker LLM
does not see it.
"""

from __future__ import annotations

import asyncio
import sys

from tenacity import (
    AsyncRetrying,
    Retrying,
    TryAgain,
    retry_never,
    stop_after_attempt,
)


def _run_sync_case() -> bool:
    attempts: list[int] = []

    def op():
        attempts.append(1)
        try:
            raise ValueError("underlying problem")
        except ValueError:
            raise TryAgain

    try:
        for attempt in Retrying(
            retry=retry_never,
            stop=stop_after_attempt(2),
            reraise=True,
        ):
            with attempt:
                op()
    except ValueError as e:
        ok_attempts = len(attempts) == 2
        ok_msg = "underlying" in str(e)
        if ok_attempts and ok_msg:
            print("[PASS] sync: underlying ValueError reraised after exhaustion")
            return True
        print(f"[FAIL] sync: got ValueError but attempts={len(attempts)} msg={e!r}")
        return False
    except TryAgain:
        print("[FAIL] sync: still raising TryAgain (bug not fixed)")
        return False
    except BaseException as e:
        print(f"[FAIL] sync: unexpected exception {type(e).__name__}: {e}")
        return False
    print("[FAIL] sync: no exception raised at all")
    return False


async def _run_async_case() -> bool:
    attempts: list[int] = []

    async def op():
        attempts.append(1)
        try:
            raise ValueError("underlying problem")
        except ValueError:
            raise TryAgain

    try:
        async for attempt in AsyncRetrying(
            retry=retry_never,
            stop=stop_after_attempt(2),
            reraise=True,
        ):
            with attempt:
                await op()
    except ValueError as e:
        ok_attempts = len(attempts) == 2
        ok_msg = "underlying" in str(e)
        if ok_attempts and ok_msg:
            print("[PASS] async: underlying ValueError reraised after exhaustion")
            return True
        print(f"[FAIL] async: got ValueError but attempts={len(attempts)} msg={e!r}")
        return False
    except TryAgain:
        print("[FAIL] async: still raising TryAgain (bug not fixed)")
        return False
    except BaseException as e:
        print(f"[FAIL] async: unexpected exception {type(e).__name__}: {e}")
        return False
    print("[FAIL] async: no exception raised at all")
    return False


def _run_regression_guard() -> bool:
    """Ordinary retry-then-success should still work."""
    state = {"calls": 0}

    def op():
        state["calls"] += 1
        if state["calls"] < 2:
            raise TryAgain
        return "ok"

    try:
        for attempt in Retrying(stop=stop_after_attempt(3), reraise=True):
            with attempt:
                result = op()
        if state["calls"] == 2 and result == "ok":
            print("[PASS] regression guard: retry-then-success still works")
            return True
        print(f"[FAIL] regression guard: calls={state['calls']} result={result!r}")
        return False
    except BaseException as e:
        print(f"[FAIL] regression guard: unexpected {type(e).__name__}: {e}")
        return False


def main() -> int:
    ok_sync = _run_sync_case()
    ok_async = asyncio.run(_run_async_case())
    ok_reg = _run_regression_guard()
    if ok_sync and ok_async and ok_reg:
        print("\nALL ACCEPTANCE CHECKS PASSED")
        return 0
    print("\nACCEPTANCE FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
