#!/usr/bin/env python3
"""Demo coding agent for AX: makes a project's failing tests pass.

It never holds a model key. It sends prompts to the model gateway named by
AX_MODEL_GATEWAY_URL, which adds the key on the way out.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

WORKSPACE = pathlib.Path(os.environ.get("AX_WORKSPACE", "/workspace"))
GATEWAY = os.environ["AX_MODEL_GATEWAY_URL"].rstrip("/")
GOAL = os.environ.get("AX_GOAL", "Make the failing tests pass.")
TASK = os.environ.get("AX_TASK_NAME", "unknown")
MAX_ROUNDS = 3
MAX_TOKENS = 8000
RESULT_FILE = WORKSPACE / ".ax-result.json"

SYSTEM = """You are a careful software engineer working in a sandbox.
You get a goal, the project's files and the output of its tests.
Reply with one JSON object and nothing else:
{"summary": "<one or two sentences on what you changed and why>",
 "files": {"<path relative to the project>": "<the whole new file content>"}}
Only include files you change. Follow AGENTS.md. Never change files under tests/."""


def log(message):
    print(f"[agent] {message}", flush=True)


def finish_checkouts():
    """Checks out repos the runner set up but couldn't fetch.

    AX prepares a workspace when the task is created, before Portainer can give
    the task its egress policy, so the runner's fetch can fail. By the time the
    agent runs, egress is in place and the fetch can be retried.
    """
    for git_dir in sorted(WORKSPACE.glob("*/.git")):
        repo = git_dir.parent
        if any(path.name != ".git" for path in repo.iterdir()):
            continue
        log(f"finishing the checkout of {repo.name}")
        subprocess.run(["git", "fetch", "--depth", "1", "origin", "HEAD"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "advice.detachedHead=false", "checkout", "-f", "FETCH_HEAD"], cwd=repo, check=True)


def find_project():
    """The project is the directory holding AGENTS.md, wherever the workspace cloned it."""
    for agents in sorted(WORKSPACE.rglob("AGENTS.md")):
        if ".git" not in agents.parts:
            return agents.parent
    sys.exit("no AGENTS.md found under the workspace")


def run_tests(project):
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=project,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout + result.stderr


def project_files(project):
    files = {}
    for path in sorted(project.rglob("*")):
        if path.is_file() and ".git" not in path.parts and path.suffix in {".py", ".md"}:
            files[str(path.relative_to(project))] = path.read_text()
    return files


def ask(prompt):
    body = json.dumps({"system": SYSTEM, "prompt": prompt, "maxTokens": MAX_TOKENS}).encode()
    request = urllib.request.Request(
        f"{GATEWAY}/v1/complete",
        data=body,
        headers={"Content-Type": "application/json", "X-AX-Task": TASK},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)["text"]


def parse_reply(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("the model did not reply with JSON")
    reply = json.loads(match.group(0))
    return reply.get("summary", ""), reply.get("files", {})


def apply_files(project, files):
    for name, content in files.items():
        path = (project / name).resolve()
        if project.resolve() not in path.parents or "tests" in path.relative_to(project.resolve()).parts:
            log(f"skipping {name}: outside the project or a test file")
            continue
        path.write_text(content)
        log(f"updated {name}")


def git_diff(project):
    result = subprocess.run(["git", "diff"], cwd=project, capture_output=True, text=True)
    return result.stdout


def main():
    finish_checkouts()
    project = find_project()
    log(f"goal: {GOAL}")
    log(f"project: {project}")

    summaries = []
    passed, output = run_tests(project)
    rounds = 0
    while not passed and rounds < MAX_ROUNDS:
        rounds += 1
        log(f"round {rounds}: tests fail, asking the model")
        files = project_files(project)
        prompt = (
            f"Goal: {GOAL}\n\nFiles:\n{json.dumps(files, indent=2)}\n\n"
            f"Test output:\n{output}"
        )
        try:
            summary, changes = parse_reply(ask(prompt))
        except Exception as err:  # reported in the result, so the user sees why
            log(f"the model call failed: {err}")
            summaries.append(f"The model call failed: {err}")
            break
        summaries.append(summary)
        log(f"model: {summary}")
        apply_files(project, changes)
        passed, output = run_tests(project)

    status = "succeeded" if passed else "failed"
    result = {
        "status": status,
        "rounds": rounds,
        "summary": " ".join(summaries) or "Tests already pass; nothing to change.",
        "diff": git_diff(project),
        "testOutput": output,
    }
    RESULT_FILE.write_text(json.dumps(result, indent=2))
    log(f"{status} after {rounds} round(s); result in {RESULT_FILE}")
    print(result["diff"], flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
