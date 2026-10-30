# shopkit (demo repo)

A small Python library the agent practises on. It has passing tests but contains bugs on
purpose. Each bug is described by an issue in `../benchmark/issues.jsonl`, written the way
a user would report it, and checked by a hidden test in `../benchmark/hidden_tests/` that
the agent never sees.

```bash
python -m pytest
```
