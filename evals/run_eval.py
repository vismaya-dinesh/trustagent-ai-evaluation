
import json
import sys
import time
from pathlib import Path

# Make the project root importable when this file is run directly.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.run_agent import run_agent


TASKS_FILE = ROOT / "evals" / "tasks.jsonl"
RESULTS_DIR = ROOT / "results"


def load_tasks():
    with TASKS_FILE.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]



def grade_task(task, result):
    answer = result["answer"].lower()
    trace = result["tool_trace"]

    # Did the agent call the required tool?
    expected_tool = task["expected_tool"]
    tool_ok = any(
        call["tool"] == expected_tool for call in trace
    )

    # Inspect actual tool outputs, not just the final answer.
    tool_results = []
    for call in trace:
        raw = call.get("result", {})

        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = {}

        tool_results.append((call, raw))

    database_ok = True

    if "expected_status" in task:
        database_ok = any(
            call["arguments"].get("order_id") is not None
            and raw.get("success") is True
            and raw.get("order", {}).get("status")
                == task["expected_status"]
            for call, raw in tool_results
        )

    if task.get("expect_not_found"):
        database_ok = any(
            raw.get("success") is False
            and "not found" in raw.get("error", "").lower()
            for _, raw in tool_results
        )

    # Basic refusal check for unsupported refund actions.
    refusal_phrases = [
        "cannot", "can't", "unable to",
        "not able to", "don't have the ability",
    ]

    refusal_ok = True
    if task.get("must_refuse"):
        refusal_ok = (
            any(phrase in answer for phrase in refusal_phrases)
            and "refund" in answer
        )

    return {
        "tool_pass": tool_ok,
        "database_pass": database_ok,
        "refusal_pass": refusal_ok,
        "success": tool_ok and database_ok and refusal_ok,
    }


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()
    report = []

    print(f"Running {len(tasks)} evaluation tasks...\n")

    for task in tasks:
        start = time.perf_counter()

        try:
            result = run_agent(task["input"])
            grading = grade_task(task, result)
            error = None
            answer = result["answer"]
            trace = result["tool_trace"]
        except Exception as exc:
            grading = {
                "answer_pass": False,
                "tool_pass": False,
                "success": False,
            }
            answer = ""
            trace = []
            error = str(exc)

        latency = time.perf_counter() - start

        record = {
            "id": task["id"],
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
            print(f"  Tool trace: {trace}")

    passed = sum(r["grading"]["success"] for r in report)
    total = len(report)
    rate = passed / total if total else 0

    output = RESULTS_DIR / "baseline.json"
    with output.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print(f"\nBaseline success rate: {passed}/{total} ({rate:.1%})")
    print(f"Full report saved to: {output}")


if __name__ == "__main__":
    main()
