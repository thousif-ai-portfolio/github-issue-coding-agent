"""Command line: list issues, or ask the agent to suggest a fix for one.

python -m agent.cli issues --demo
python -m agent.cli suggest --demo 3
python -m agent.cli suggest owner/name 12
"""

import argparse
import sys

from agent.config import get_settings
from agent.main import get_llm, get_store
from agent.pipeline import execute_run
from agent.targets import resolve_target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    issues = commands.add_parser("issues", help="List open issues")
    suggest = commands.add_parser("suggest", help="Suggest a fix for an issue")
    for command in (issues, suggest):
        group = command.add_mutually_exclusive_group(required=True)
        group.add_argument("repo", nargs="?", help="GitHub repository as owner/name")
        group.add_argument("--demo", action="store_true", help="Use the bundled demo repo")
    suggest.add_argument("number", type=int, help="Issue number")
    args = parser.parse_args(argv)

    settings = get_settings()
    target = resolve_target("demo" if args.demo else "github", args.repo, settings)
    if args.command == "issues":
        for issue in target.issues.list_open():
            print(f"#{issue.number:<4} {issue.title}")
        return 0

    store, llm = get_store(), get_llm()
    run_id = store.create_run(target.label, args.number, llm.model)
    print(f"Run {run_id}: working on issue #{args.number} with {llm.model}.")
    print("This takes a few minutes on a CPU.\n")
    execute_run(run_id, args.number, target, llm, store, settings)

    run = store.get_run(run_id)
    for step in run["steps"]:
        print(f"  {step['name']:<18} {step['status']:<6} {step['duration_ms'] / 1000:6.1f}s")
    print(f"\nStatus: {run['status']}")
    if run["error"]:
        print(f"Error: {run['error']}")
    if run["explanation"]:
        print(f"\n{run['explanation']}")
    if run["diff"]:
        print(f"\n{run['diff']}")
    return 0 if run["status"] in ("suggested", "skipped") else 1


if __name__ == "__main__":
    sys.exit(main())
