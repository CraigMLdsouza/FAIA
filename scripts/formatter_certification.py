#!/usr/bin/env python3

import subprocess
import datetime
import sys
from pathlib import Path

LOG_FILE = (
    f"result_formatter_certification_"
    f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

TESTS = [
    {
        "name": "Formatter Self Test Harness",
        "command": [
            "python",
            "result_formatter.py",
            "--run-tests"
        ]
    }
]


def log_write(text):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def run_test(test):

    result = subprocess.run(
        test["command"],
        capture_output=True,
        text=True
    )

    success = result.returncode == 0

    log_write("=" * 80)
    log_write(f"TEST: {test['name']}")
    log_write("=" * 80)

    log_write("\nSTDOUT:\n")
    log_write(result.stdout)

    log_write("\nSTDERR:\n")
    log_write(result.stderr)

    log_write(f"\nRETURN CODE: {result.returncode}\n")

    return success


def main():

    print("\n=== RESULT FORMATTER GOLD MASTER CERTIFICATION ===\n")

    log_write("=" * 80)
    log_write("RESULT FORMATTER GOLD MASTER CERTIFICATION")
    log_write("=" * 80)

    passed = 0
    failed = 0

    for idx, test in enumerate(TESTS, start=1):

        ok = run_test(test)

        if ok:
            print(f"[PASS] {idx:02d} - {test['name']}")
            passed += 1
        else:
            print(f"[FAIL] {idx:02d} - {test['name']}")
            failed += 1

    print("\n========================================")
    print(f"PASSED : {passed}")
    print(f"FAILED : {failed}")
    print("========================================")

    log_write(f"\nPASSED : {passed}")
    log_write(f"FAILED : {failed}")

    if failed == 0:

        print("\nFAIA_RESULT_FORMATTER_v1.0.2_GOLD_MASTER")
        print("STATUS: CERTIFIED")

        log_write(
            "\nFAIA_RESULT_FORMATTER_v1.0.2_GOLD_MASTER\n"
            "STATUS: CERTIFIED"
        )

        exit_code = 0

    else:

        print("\nSTATUS: CERTIFICATION FAILED")

        log_write("\nSTATUS: CERTIFICATION FAILED")

        exit_code = 1

    print(f"\nDetailed log: {LOG_FILE}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()