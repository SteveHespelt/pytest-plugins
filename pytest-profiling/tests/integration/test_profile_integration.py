from distutils.dir_util import copy_tree
import re
import shutil

from pkg_resources import resource_filename, get_distribution
import pytest

from pytest_virtualenv import VirtualEnv

# SJH - Setuptools 52.0.0 removed the easy_install command, not available in the created virtualenv /bin anymore, use pip


@pytest.yield_fixture(scope="session")
def virtualenv():
    with VirtualEnv() as venv:
        test_dir = resource_filename("pytest_profiling", "tests/integration/profile")

        venv.install_package("more-itertools", installer='pip install')

        # Keep pytest version the same as what's running this test to ensure P27 keeps working
        venv.install_package("pytest=={}".format(get_distribution("pytest").version), installer='pip install' )

        venv.install_package("pytest-cov", installer='pip install')
        venv.install_package("gprof2dot", installer='pip install')
        venv.install_package("pytest-profiling", installer='pip install')
        copy_tree(test_dir, venv.workspace)
        shutil.rmtree(
            venv.workspace / "tests" / "unit" / "__pycache__", ignore_errors=True
        )
        yield venv


def test_profile_profiles_tests(pytestconfig, virtualenv):
    output = virtualenv.run_with_coverage(
        ["-m", "pytest", "--profile", "tests/unit/test_example.py"],
        pytestconfig,
        cd=virtualenv.workspace,
    )
    assert "test_example.py:1(test_foo)" in output


def test_profile_generates_svg(pytestconfig, virtualenv):
    output = virtualenv.run_with_coverage(
        ["-m", "pytest", "--profile-svg", "tests/unit/test_example.py"],
        pytestconfig,
        cd=virtualenv.workspace,
        capture_stderr=True
    )
    assert any(
        [
            "test_example:1:test_foo" in i
            for i in (virtualenv.workspace / "prof/combined.svg").lines()
        ]
    )

    assert "test_example.py:1(test_foo)" in output
    assert "SVG" in output


def test_profile_long_name(pytestconfig, virtualenv):
    output = virtualenv.run_with_coverage(
        ["-m", "pytest", "--profile", "tests/unit/test_long_name.py"],
        pytestconfig,
        cd=virtualenv.workspace,
    )
    assert (virtualenv.workspace / "prof/fbf7dc37.prof").isfile()


def test_profile_chdir(pytestconfig, virtualenv):
    output = virtualenv.run_with_coverage(
        ["-m", "pytest", "--profile", "tests/unit/test_chdir.py"],
        pytestconfig,
        cd=virtualenv.workspace,
    )


def test_profile_callers_mode(pytestconfig, virtualenv):
    output = virtualenv.run_with_coverage(
        ["-m", "pytest", "--profile", "--profiling-mode=callers", "tests/unit/test_example.py"],
        pytestconfig,
        cd=virtualenv.workspace,
    )

    # default sort key: cumulative
    assert "test_example.py:1(test_foo)" in output
    assert "called..." in output
    assert "Ordered by: cumulative time" in output


def test_profile_callees_mode(pytestconfig, virtualenv):
    output = virtualenv.run_with_coverage(
        ["-m", "pytest", "--profile", "--profiling-mode=callees", "tests/unit/test_example.py"],
        pytestconfig,
        cd=virtualenv.workspace,
    )

    # default sort key: cumulative
    assert "test_example.py:1(test_foo)" in output
    assert "was called by..." in output
    assert "Ordered by: cumulative time" in output


def test_profile_multiple_sort_keys(pytestconfig, virtualenv):
    """And because we use the --profiling-filter, we get that function in our output - to assert its presence.
    """
    output = virtualenv.run_with_coverage(
        ["-m", "pytest", "--profile", "--profiling-sort-key=file", "--profiling-sort-key=name",
         "--profiling-filter=test_foo", "tests/unit/test_example.py"],
        pytestconfig,
        cd=virtualenv.workspace,
    )

    # default sort key: cumulative
    assert "test_example.py:1(test_foo)" in output
    assert "Ordered by: file name, function name" in output


def test_profile_number_elements(pytestconfig, virtualenv):
    output = virtualenv.run_with_coverage(
        ["-m", "pytest", "--profile", "--element-number=5", "tests/unit/test_example.py"],
        pytestconfig,
        cd=virtualenv.workspace,
    )

    # default sort key: cumulative
    assert "Ordered by: cumulative time" in output
    # List reduced from 56 to 5 due to restriction <5>
    re_pattern = re.compile('List reduced from [0-9][0-9]* to 5 due to restriction <5>')
    assert re_pattern.search(output) is not None

