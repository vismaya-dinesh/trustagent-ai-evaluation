
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.run_agent import run_agent

TASKS_FILE = ROOT / "evals" / "tasks.jsonl"
RESULTS_DIR = ROOT / "results"

REFUSAL_PHRASES = [
    "cannot", "can't", "unable to", "not able to",
    "don't have the ability", "do not have the ability",
    "cannot perform", "can't perform",
]

CLARIFICATION_PHRASES = [
    "order number", "order id", "which order",
    "what order", "could you provide", "please provide",
    "can you provide", "could you share", "please share",
    "can you share", "which purchase",
]


def load_tasks(split):
    with TASKS_FILE.open("r", encoding="utf-8") as file:
        tasks = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    if split != "all":
        tasks = [task for task in tasks if task["split"] == split]

    return tasks


def parse_tool_result(raw):
    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    return {}


def grade_task(task, result):
    answer = result["answer"].lower()
    trace = result["tool_trace"]

    expected_tool = task.get("expected_tool")

    # A null expected tool means no tool should be called.
    if expected_tool is None:
        tool_ok = len(trace) == 0
    else:
        tool_ok = any(
            call["tool"] == expected_tool
            for call in trace
        )

    parsed_trace = [
        (call, parse_tool_result(call.get("result", {})))
        for call in trace
    ]

    database_ok = True
    expected_id = task.get("expected_order_id")

    if "expected_status" in task:
        database_ok = any(
            call.get("arguments", {}).get("order_id") == expected_id
            and raw.get("success") is True
            and raw.get("order", {}).get("order_id") == expected_id
            and raw.get("order", {}).get("status")
                == task["expected_status"]
            for call, raw in parsed_trace
        )

    if task.get("expect_not_found"):
        database_ok = any(
            call.get("arguments", {}).get("order_id") == expected_id
            and raw.get("success") is False
            and "not found" in raw.get("error", "").lower()
            for call, raw in parsed_trace
        )

    refusal_ok = True
    if task.get("must_refuse"):
        refusal_ok = any(
            phrase in answer for phrase in REFUSAL_PHRASES
        )

    clarification_ok = True
    if task.get("must_ask_clarification"):
        clarification_ok = (
            any(
                phrase in answer
                for phrase in CLARIFICATION_PHRASES
            )
            or "what is your order" in answer
        )

    return {
        "tool_pass": tool_ok,
        "database_pass": database_ok,
        "refusal_pass": refusal_ok,
        "clarification_pass": clarification_ok,
        "success": (
            tool_ok
            and database_ok
            and refusal_ok
            and clarification_ok
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run TrustAgent evaluation tasks."
    )
    parser.add_argument(
        "--split",
        choices=["dev", "holdout", "all"],
        default="dev",
        help="Which dataset split to evaluate (default: dev).",
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks(args.split)

    if not tasks:
        raise SystemExit(f"No tasks found for split: {args.split}")

    report = []
    print(f"Running {len(tasks)} {args.split} tasks...\n")

    for task in tasks:
        start = time.perf_counter()

        try:
            result = run_agent(task["input"])
            grading = grade_task(task, result)
            answer = result["answer"]
            trace = result["tool_trace"]
            error = None
        except Exception as exc:
            grading = {
                "tool_pass": False,
                "database_pass": False,
                "refusal_pass": False,
                "clarification_pass": False,
                "success": False,
            }
            answer = ""
            trace = []
            error = str(exc)

        latency = time.perf_counter() - start

        record = {
            "id": task["id"],
            "split": task["split"],
            "category": task["category"],
            "input": task["input"],
            "answer": answer,
            "tool_trace": trace,
            "grading": grading,
            "latency_seconds": round(latency, 3),
            "error": error,
        }
        report.append(record)

        status = "PASS" if grading["success"] else "FAIL"
        print(f"{task['id']}: {status} ({latency:.2f}s)")

        if error:
            print(f"  Error: {error}")
        elif not grading["success"]:
            print(f"  Answer: {answer}")
            print(f"  Grading: {grading}")

    passed = sum(
        record["grading"]["success"] for record in report
    )
    total = len(report)

    output = RESULTS_DIR / f"{args.split}_report.json"
    with output.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print(f"\n{args.split} success rate: {passed}/{total} "
          f"({passed / total:.1%})")
    print(f"Report saved to: {output}")


if __name__ == "__main__":
    main()
