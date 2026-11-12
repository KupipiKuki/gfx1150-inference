"""Deliberately failing test for the required GPU-check red-team proof."""

import pytest


pytestmark = pytest.mark.gpu


def test_required_gpu_check_blocks_on_failure() -> None:
    assert False, "red-team sentinel: the required GPU check must fail"
