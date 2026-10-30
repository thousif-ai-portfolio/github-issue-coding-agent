import pytest

from agent.config import Settings
from agent.edits import EditError, apply_edits, make_diff
from agent.schemas import Edit
from agent.workspace import WorkspaceError, list_source_files, rank_files, read_file

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
