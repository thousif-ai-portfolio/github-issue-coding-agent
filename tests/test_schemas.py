import pytest
from pydantic import ValidationError

from agent.schemas import TestProposal
from tests.conftest import MEDIAN_TEST


def test_test_proposal_needs_test_source_not_a_path():
    assert TestProposal(code=MEDIAN_TEST).code == MEDIAN_TEST
    # What qwen2.5-coder:3b replied in every benchmark run before this check existed.
    with pytest.raises(ValidationError, match="not a file name"):
        TestProposal(code="tests/test_agent_issue_8.py")
