import subprocess

import pytest

from agent.config import Settings
from agent.edits import EditError, apply_edits, make_diff
from agent.graph import _line_endings_like
from agent.sandbox import copy_repo
from agent.schemas import Edit
from agent.store import Store
from agent.workspace import (
    WorkspaceError,
    is_test_file,
    list_source_files,
    rank_files,
    read_file,
)

DEMO = Settings().demo_repo


def test_lists_python_files_with_forward_slashes():
    files = list_source_files(DEMO)
    assert "shopkit/stats.py" in files
    assert "tests/test_shopkit.py" in files


def test_rank_files_puts_the_named_function_first_and_skips_tests():
    ranked = rank_files(DEMO, "median is wrong for an even number of values", limit=8)
    assert ranked[0] == "shopkit/stats.py"
    assert not any(rel.startswith("tests/") for rel in ranked)


def test_read_file_refuses_paths_outside_the_repo():
    with pytest.raises(WorkspaceError):
        read_file(DEMO, "../agent/config.py")


def test_apply_edits_and_diff(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    edit = Edit(file="calc.py", find="    return a - b\n", replace="    return a + b\n")
    changed = apply_edits(tmp_path, [edit], ["calc.py"])
    assert changed["calc.py"] == "def add(a, b):\n    return a + b\n"
    diff = make_diff(tmp_path, changed)
    assert "-    return a - b" in diff and "+    return a + b" in diff
    # Suggestions are never written to disk.
    assert "a - b" in (tmp_path / "calc.py").read_text()


def test_diff_applies_with_git_when_files_lack_a_final_newline(tmp_path):
    # The model's tests usually end without a newline; the saved patch must still apply.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n", newline="\n")
    changed = {
        "calc.py": "def add(a, b):\n    return a + b",
        "tests/test_calc.py": (
            "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3"
        ),
    }
    patch = tmp_path / "fix.diff"
    patch.write_text(make_diff(repo, changed), encoding="utf-8", newline="\n")

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    result = subprocess.run(["git", "apply", str(patch)], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    for rel, content in changed.items():
        assert (repo / rel).read_text(encoding="utf-8") == content


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (Edit(file="other.py", find="x", replace="y"), "not one of the files"),
        (Edit(file="calc.py", find="missing", replace="y"), "not found"),
        (Edit(file="calc.py", find="return", replace="yield"), "appears 2 times"),
        (Edit(file="calc.py", find="return 1", replace="return 1"), "do not change anything"),
        (
            Edit(file="calc.py", find="    return 1\n", replace="if True:\nreturn 1\n"),
            "not valid Python",
        ),
        # The real model did this: parses, but 'return' ends up outside the function.
        (
            Edit(file="calc.py", find="    return 1\n", replace="if True:\n    return 1\n"),
            "not valid Python",
        ),
    ],
)
def test_apply_edits_explains_what_is_wrong(tmp_path, edit, message):
    (tmp_path / "calc.py").write_text("def a():\n    return 1\n\ndef b():\n    return 2\n")
    with pytest.raises(EditError, match=message):
        apply_edits(tmp_path, [edit], ["calc.py"])


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/test_cart.py", True),
        ("conftest.py", True),
        ("test/helpers.py", True),
        ("shopkit/cart_test.py", True),
        ("shopkit/cart.py", False),
        ("shopkit/testing_utils.py", False),
    ],
)
def test_is_test_file_covers_pytest_config_and_test_folders(path, expected):
    assert is_test_file(path) is expected


def test_folders_named_like_python_files_are_not_listed(tmp_path):
    (tmp_path / "pkg.py").mkdir()
    (tmp_path / "real.py").write_text("x = 1\n")
    assert list_source_files(tmp_path) == ["real.py"]


def test_a_crlf_file_keeps_crlf_in_the_pr(tmp_path):
    original = tmp_path / "a.py"
    original.write_bytes(b"x = 1\r\ny = 2\r\n")
    assert _line_endings_like(original, "x = 1\ny = 3\n") == "x = 1\r\ny = 3\r\n"
    original.write_bytes(b"x = 1\n")
    assert _line_endings_like(original, "x = 2\n") == "x = 2\n"


def test_symlinks_are_not_copied_into_the_sandbox(tmp_path):
    repo, outside = tmp_path / "repo", tmp_path / "secret.txt"
    repo.mkdir()
    outside.write_text("private")
    (repo / "a.py").write_text("x = 1\n")
    try:
        (repo / "link.txt").symlink_to(outside)
    except OSError:
        pytest.skip("creating symlinks needs extra rights on this machine")
    copy_repo(repo, tmp_path / "copy", {})
    assert sorted(p.name for p in (tmp_path / "copy").iterdir()) == ["a.py"]


def test_a_run_can_be_claimed_for_review_only_once(tmp_path):
    store = Store(tmp_path / "agent.db")
    run_id = store.create_run("demo", 1, "m")
    store.update_run(run_id, status="awaiting_approval")
    assert store.claim_for_review(run_id) is True
    assert store.claim_for_review(run_id) is False


def test_runs_cut_off_by_a_restart_are_marked_failed(tmp_path):
    store = Store(tmp_path / "agent.db")
    run_id = store.create_run("demo", 1, "m")
    store.fail_interrupted()
    assert store.get_run(run_id)["status"] == "failed"
