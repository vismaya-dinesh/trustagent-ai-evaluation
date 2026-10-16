
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from sidebar import render_sidebar


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent
EVAL_SCRIPT = ROOT / "evals" / "run_eval.py"
DEV_REPORT = ROOT / "results" / "dev_report.json"
HOLDOUT_REPORT = ROOT / "results" / "holdout_report.json"

st.set_page_config(
    page_title="TrustAgent | Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------
# STYLING
# --------------------------------------------------

st.markdown(
    """
    <style>
    @keyframes taFadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        animation: taFadeIn 0.4s ease-out;
    }

    .ta-eyebrow {
        color: #93c5fd;
        text-transform: uppercase;
        letter-spacing: 0.13em;
        font-size: 0.76rem;
        font-weight: 700;
    }

    .ta-title {
        font-size: clamp(2rem, 4vw, 3rem);
        font-weight: 800;
        letter-spacing: -0.045em;
        line-height: 1.15;
        margin: 0.4rem 0;
    }

    .ta-subtitle {
        color: #a7b4c8;
        font-size: 1.02rem;
        margin-bottom: 1.5rem;
    }

    [data-testid="stMetric"] {
        background: #111b2e;
        border: 1px solid #26364e;
        border-radius: 14px;
        padding: 16px;
        transition: transform 0.18s ease, border-color 0.18s ease;
    }

    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: #4264a3;
    }

    div.stButton > button {
        border-radius: 10px;
        min-height: 2.6rem;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #26364e;
        border-radius: 10px;
        overflow: hidden;
    }

    @media (max-width: 640px) {
        .block-container {
            padding: 1rem 0.75rem 2rem;
        }

        [data-testid="stMetric"] {
            padding: 12px;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            transition-duration: 0.01ms !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# REPORT HELPERS
# --------------------------------------------------

def load_report(path: Path):
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return None


def get_records(report):
    if report is None:
        return []

    if isinstance(report, list):
        return [item for item in report if isinstance(item, dict)]

    if not isinstance(report, dict):
        return []

    for key in ("results", "tasks", "task_results", "details", "cases"):
        value = report.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    raw_report = report.get("raw_report")
    if isinstance(raw_report, list):
        return [item for item in raw_report if isinstance(item, dict)]

    return []


def task_succeeded(record):
    grading = record.get("grading", {})

    if isinstance(grading, dict) and "success" in grading:
        return bool(grading["success"])

    if "passed" in record:
        return bool(record["passed"])

    if "success" in record:
        return bool(record["success"])

    status = str(record.get("status", "")).strip().lower()

    if status in {"pass", "passed", "success", "successful"}:
        return True

    if status in {"fail", "failed", "error"}:
        return False

    return None


def report_metrics(report):
    records = get_records(report)
    outcomes = [task_succeeded(record) for record in records]

    passed = sum(value is True for value in outcomes)
    failed = sum(value is False for value in outcomes)
    unknown = sum(value is None for value in outcomes)

    latencies = []
    for record in records:
        value = record.get(
            "latency_seconds",
            record.get("latency"),
        )
        try:
            if value is not None:
                latencies.append(float(value))
        except (TypeError, ValueError):
            pass

    known = passed + failed

    return {
        "total": len(records),
        "passed": passed,
        "failed": failed,
        "unknown": unknown,
        "rate": passed / known * 100 if known else None,
        "avg_latency": (
            sum(latencies) / len(latencies) if latencies else None
        ),
        "records": records,
    }


def format_metric(value, suffix=""):
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


def render_metrics(metrics):
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Success rate", format_metric(metrics["rate"], "%"))
    c2.metric("Passed", metrics["passed"])
    c3.metric("Failed", metrics["failed"])
    c4.metric("Average latency", format_metric(metrics["avg_latency"], " s"))


def render_report_explorer(metrics, prefix):
    records = metrics["records"]

    if not records:
        st.info("No task-level results are available in this report.")
        return

    rows = []

    for record in records:
        outcome = task_succeeded(record)
        grading = record.get("grading", {})
        trace = record.get("tool_trace", [])

        if isinstance(trace, list):
            trace_text = " → ".join(str(item) for item in trace)
        else:
            trace_text = str(trace) if trace else ""

        answer = record.get("answer", "")
        if not isinstance(answer, str):
            answer = json.dumps(answer, ensure_ascii=False)

        latency = record.get(
            "latency_seconds",
            record.get("latency"),
        )

        rows.append({
            "ID": str(record.get("id", "—")),
            "Category": str(record.get("category", "—")),
            "Status": (
                "PASS" if outcome is True
                else "FAIL" if outcome is False
                else "UNKNOWN"
            ),
            "Latency (s)": latency,
            "Answer": answer,
            "Tool trace": trace_text,
            "Grading": json.dumps(grading, ensure_ascii=False),
        })

    frame = pd.DataFrame(rows)

    left, right = st.columns(2)

    with left:
        status_filter = st.selectbox(
            "Status",
            ["All", "PASS", "FAIL", "UNKNOWN"],
            key=f"{prefix}_status",
        )

    with right:
        categories = sorted(frame["Category"].unique().tolist())
        category_filter = st.selectbox(
            "Category",
            ["All"] + categories,
            key=f"{prefix}_category",
        )

    filtered = frame.copy()

    if status_filter != "All":
        filtered = filtered[filtered["Status"] == status_filter]

    if category_filter != "All":
        filtered = filtered[filtered["Category"] == category_filter]

    st.caption(f"Showing {len(filtered)} of {len(frame)} tasks.")

    st.dataframe(
        filtered[["ID", "Category", "Status", "Latency (s)"]],
        use_container_width=True,
        hide_index=True,
    )

    if not filtered.empty:
        with st.expander("Inspect a task"):
            selected_id = st.selectbox(
                "Task ID",
                filtered["ID"].tolist(),
                key=f"{prefix}_task_id",
            )

            selected = filtered[filtered["ID"] == selected_id].iloc[0]

            st.markdown("**Answer**")
            st.write(selected["Answer"] or "No answer recorded.")

            st.markdown("**Tool trace**")
            st.code(selected["Tool trace"] or "No tool calls recorded.")

            st.markdown("**Grading details**")
            st.code(selected["Grading"], language="json")


# --------------------------------------------------
# STREAMING PROCESS HELPERS
# --------------------------------------------------

def read_process_output(stream, output_queue):
    """Read output in a background thread to keep the UI responsive."""
    try:
        for line in iter(stream.readline, ""):
            output_queue.put(line.rstrip("\r\n"))
    except Exception as exc:
        output_queue.put(f"[Output reader error] {exc}")
    finally:
        output_queue.put(None)


def run_dev_evaluation():
    if not EVAL_SCRIPT.exists():
        st.error(f"Evaluation script not found: {EVAL_SCRIPT}")
        return

    st.session_state["eval_output"] = ""
    logs = []
    output_queue = queue.Queue()
    completed_tasks = 0
    total_tasks = 35
    timeout_seconds = 900
    start_time = time.monotonic()
    process = None
    reader_thread = None
    stream_finished = False
    timed_out = False

    status = st.status("Starting development evaluation…", expanded=True)
    progress = st.progress(0, text=f"Tasks completed: 0/{total_tasks}")
    activity = st.empty()
    elapsed_display = st.empty()
    log_display = st.empty()

    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"

    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                str(EVAL_SCRIPT),
                "--split",
                "dev",
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=environment,
        )

        if process.stdout is None:
            raise RuntimeError("Unable to read evaluation output.")

        reader_thread = threading.Thread(
            target=read_process_output,
            args=(process.stdout, output_queue),
            daemon=True,
        )
        reader_thread.start()

        while True:
            elapsed = time.monotonic() - start_time

            if elapsed >= timeout_seconds and process.poll() is None:
                timed_out = True
                process.terminate()
                logs.append(
                    f"Evaluation timed out after {timeout_seconds} seconds."
                )

            try:
                line = output_queue.get(timeout=0.2)
            except queue.Empty:
                line = "__NO_NEW_LINE__"

            if line is None:
                stream_finished = True
            elif line != "__NO_NEW_LINE__":
                logs.append(line)

                total_match = re.search(
                    r"Running\s+(\d+)\s+dev\s+tasks",
                    line,
                    re.IGNORECASE,
                )
                if total_match:
                    total_tasks = int(total_match.group(1))

                task_match = re.search(
                    r"\bT\d+\s*:\s*(PASS|FAIL|ERROR)\b",
                    line,
                    re.IGNORECASE,
                )
                if task_match:
                    completed_tasks += 1

                activity.markdown(f"**Latest output:** {line[:350]}")

            elapsed = time.monotonic() - start_time
            elapsed_display.caption(f"Elapsed time: {elapsed:.1f} seconds")

            progress.progress(
                min(completed_tasks / max(total_tasks, 1), 1.0),
                text=f"Tasks completed: {completed_tasks}/{total_tasks}",
            )

            log_display.code("\n".join(logs[-18:]), language="text")

            if stream_finished and process.poll() is not None:
                break

            if timed_out and process.poll() is not None and stream_finished:
                break

        return_code = process.wait(timeout=10)

        if timed_out:
            return_code = 1
        elif return_code == 0:
            progress.progress(1.0, text="Evaluation process completed.")
            status.update(
                label="Development evaluation completed.",
                state="complete",
                expanded=False,
            )
        else:
            status.update(
                label="Development evaluation failed. Check the logs.",
                state="error",
                expanded=True,
            )

        st.session_state["eval_return_code"] = return_code
        st.session_state["eval_output"] = "\n".join(logs)

    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()
            process.wait()

        logs.append("The evaluation process did not exit after termination.")
        st.session_state["eval_return_code"] = 1
        st.session_state["eval_output"] = "\n".join(logs)
        status.update(
            label="Evaluation process had to be stopped.",
            state="error",
            expanded=True,
        )

    except Exception as exc:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()

        logs.append(f"{type(exc).__name__}: {exc}")
        st.session_state["eval_return_code"] = 1
        st.session_state["eval_output"] = "\n".join(logs)

        status.update(
            label="Could not complete the evaluation.",
            state="error",
            expanded=True,
        )

    finally:
        if process is not None and process.stdout is not None:
            process.stdout.close()

    if st.session_state.get("eval_return_code") == 0:
        st.success("Development evaluation finished successfully.")
    else:
        st.error("Development evaluation failed or timed out.")

    with st.expander("Complete evaluation output", expanded=True):
        st.code(
            st.session_state.get("eval_output", "") or "No output captured.",
            language="text",
        )


# --------------------------------------------------
# SIDEBAR AND HEADER
# --------------------------------------------------

render_sidebar("dashboard")

st.markdown(
    '<div class="ta-eyebrow">Agent reliability platform</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="ta-title">TrustAgent Dashboard</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="ta-subtitle">'
    'Evaluate accuracy, tool usage, safety, and response reliability.'
    '</div>',
    unsafe_allow_html=True,
)


# --------------------------------------------------
# OVERVIEW
# --------------------------------------------------

dev_report = load_report(DEV_REPORT)
holdout_report = load_report(HOLDOUT_REPORT)

dev = report_metrics(dev_report)
holdout = report_metrics(holdout_report)

st.subheader("Evaluation overview")

c1, c2, c3 = st.columns(3)

with c1:
    st.metric("Development tasks", dev["total"] or 35)

with c2:
    st.metric("Holdout tasks", holdout["total"] or 15)

with c3:
    st.metric(
        "Evaluation script",
        "Available" if EVAL_SCRIPT.exists() else "Missing",
    )

st.divider()


# --------------------------------------------------
# DEVELOPMENT EVALUATION
# --------------------------------------------------

st.subheader("Development evaluation")

st.write(
    "Run the 35-task development benchmark. Output is streamed as it "
    "arrives so you can see the latest task and progress."
)

if st.button(
    "▶ Run development evaluation",
    type="primary",
    use_container_width=True,
):
    run_dev_evaluation()
    st.rerun()

if st.session_state.get("eval_output"):
    with st.expander("Latest evaluation logs", expanded=False):
        st.code(st.session_state["eval_output"], language="text")

    if st.session_state.get("eval_return_code") == 0:
        st.success("The most recent development evaluation succeeded.")
    elif st.session_state.get("eval_return_code") is not None:
        st.error("The most recent development evaluation failed.")

st.divider()


# --------------------------------------------------
# DEVELOPMENT REPORT
# --------------------------------------------------

st.subheader("Development report")

if dev["total"]:
    render_metrics(dev)

    if dev["unknown"]:
        st.caption(
            f"{dev['unknown']} task(s) have no recognized pass/fail result."
        )

    render_report_explorer(dev, "dev")
else:
    st.info(
        "No development report found. Run the development evaluation "
        "to generate one."
    )

st.divider()


# --------------------------------------------------
# HOLDOUT REPORT — READ ONLY
# --------------------------------------------------

st.subheader("Holdout report")

st.caption(
    "This report is displayed for validation only. The dashboard does not "
    "run the holdout benchmark or tune the agent against it."
)

if holdout["total"]:
    render_metrics(holdout)

    if holdout["unknown"]:
        st.caption(
            f"{holdout['unknown']} task(s) have no recognized pass/fail result."
        )

    render_report_explorer(holdout, "holdout")
else:
    st.info("No holdout report was found.")

st.divider()
st.caption("TrustAgent · AI Agent Reliability & Evaluation System")
