#!/usr/bin/env python3

import subprocess
import json
import sys
from datetime import datetime

LOG_FILE = f"resolver_certification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


TESTS = [
    {
        "name": "Health Validation",
        "command": ["python", "repository_resolver.py", "--health"],
        "validator": lambda r: (
            r.get("validation_status") == "VALIDATED"
        )
    },

    {
        "name": "Repository Discovery - context7",
        "command": ["python", "repository_resolver.py", "context7"],
        "validator": lambda r: (
            r.get("retrieval_status") == "SUCCESS"
            and r["discovery_evidence"]["resolution_path"]
            == ["query", "repository"]
        )
    },

    {
        "name": "Repository Discovery - URL",
        "command": [
            "python",
            "repository_resolver.py",
            "github.com/upstash/context7"
        ],
        "validator": lambda r: (
            r.get("retrieval_status") == "SUCCESS"
            and r["discovery_evidence"]["resolution_path"]
            == ["query", "repository"]
        )
    },

    {
        "name": "Provider Discovery - Digital Ocean",
        "command": [
            "python",
            "repository_resolver.py",
            "Digital Ocean"
        ],
        "validator": lambda r: (
            r.get("retrieval_status") == "SUCCESS"
            and r["discovery_evidence"]["resolution_path"]
            == ["query", "provider", "repository"]
        )
    },

    {
        "name": "Provider Discovery - MCP Alias",
        "command": [
            "python",
            "repository_resolver.py",
            "mcp"
        ],
        "validator": lambda r: (
            r.get("retrieval_status") == "SUCCESS"
            and r["discovery_evidence"]["resolution_path"]
            == ["query", "provider", "repository"]
        )
    },

    {
        "name": "Provider Discovery - Token Match",
        "command": [
            "python",
            "repository_resolver.py",
            "model context protocol"
        ],
        "validator": lambda r: (
            r.get("retrieval_status") == "SUCCESS"
            and r["discovery_evidence"]["resolution_path"]
            == ["query", "provider", "repository"]
        )
    },

    {
        "name": "Capability Discovery - Workflow",
        "command": [
            "python",
            "repository_resolver.py",
            "workflow automation"
        ],
        "validator": lambda r: (
            r.get("retrieval_status") == "SUCCESS"
            and r["discovery_evidence"]["resolution_path"]
            == ["query", "capability", "provider", "repository"]
        )
    },

    {
        "name": "Capability Discovery - Issues",
        "command": [
            "python",
            "repository_resolver.py",
            "issue tracking"
        ],
        "validator": lambda r: (
            r.get("retrieval_status") == "SUCCESS"
            and r["discovery_evidence"]["resolution_path"]
            == ["query", "capability", "provider", "repository"]
        )
    },

    {
        "name": "Metadata API",
        "command": [
            "python",
            "repository_resolver.py",
            "--repository",
            "github_com_upstash_context7"
        ],
        "validator": lambda r: (
            "repository_id" in r
            and "provider_id" in r
            and "repository_url" in r
            and "installation_metadata" in r
        )
    },

    {
        "name": "Garbage Query",
        "command": [
            "python",
            "repository_resolver.py",
            "asdfghjkl"
        ],
        "validator": lambda r: (
            r.get("retrieval_status") == "NO_MATCHES_FOUND"
        )
    }
]


def write_log(text):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def extract_json(stdout_text):
    """
    Handles accidental logging around JSON.
    Attempts to locate first JSON object.
    """

    stdout_text = stdout_text.strip()

    try:
        return json.loads(stdout_text)
    except:
        pass

    start = stdout_text.find("{")
    end = stdout_text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON payload found.")

    candidate = stdout_text[start:end + 1]
    return json.loads(candidate)


def run_test(test):

    result = subprocess.run(
        test["command"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:

        error_message = (
            f"\nPROCESS FAILURE\n"
            f"RETURN CODE: {result.returncode}\n\n"
            f"STDERR:\n{result.stderr}\n\n"
            f"STDOUT:\n{result.stdout}\n"
        )

        return False, error_message

    try:
        payload = extract_json(result.stdout)

    except Exception as exc:

        return False, (
            f"\nJSON PARSE FAILURE\n"
            f"ERROR: {exc}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}\n"
        )

    try:

        passed = test["validator"](payload)

        if passed:
            return True, "PASS"

        return False, (
            "\nVALIDATION FAILURE\n"
            + json.dumps(payload, indent=2)
        )

    except Exception as exc:

        return False, (
            f"\nVALIDATOR EXCEPTION\n"
            f"{exc}\n\n"
            + json.dumps(payload, indent=2)
        )


def main():

    print("\n=== FAIA GOLD MASTER CERTIFICATION ===\n")

    write_log("=" * 80)
    write_log("FAIA GOLD MASTER CERTIFICATION")
    write_log("=" * 80)

    passed = 0
    failed = 0

    for idx, test in enumerate(TESTS, start=1):

        ok, details = run_test(test)

        if ok:

            print(f"[PASS] {idx:02d} - {test['name']}")
            write_log(f"[PASS] {idx:02d} - {test['name']}")

            passed += 1

        else:

            print(f"[FAIL] {idx:02d} - {test['name']}")

            write_log(f"[FAIL] {idx:02d} - {test['name']}")
            write_log(details)
            write_log("-" * 80)

            failed += 1

    print("\n========================================")
    print(f"PASSED : {passed}")
    print(f"FAILED : {failed}")
    print("========================================")

    write_log(f"\nPASSED: {passed}")
    write_log(f"FAILED: {failed}")

    print(f"\nDetailed log: {LOG_FILE}")

    if failed == 0:

        print("\nFAIA_REPOSITORY_RESOLVER_v2.2.1_GOLD_MASTER")
        print("STATUS: CERTIFIED")

        write_log("STATUS: CERTIFIED")

        sys.exit(0)

    else:

        print("\nSTATUS: CERTIFICATION FAILED")

        write_log("STATUS: CERTIFICATION FAILED")

        sys.exit(1)


if __name__ == "__main__":
    main()