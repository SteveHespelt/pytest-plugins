# Pytest Profiling Plugin

Profiling plugin for pytest, with tabular and heat graph output.

Tests are profiled with [cProfile](http://docs.python.org/library/profile.html#module-cProfile) and analysed with [pstats](http://docs.python.org/library/profile.html#pstats.Stats); heat graphs are
generated using [gprof2dot](https://github.com/jrfonseca/gprof2dot) and [dot](http://www.graphviz.org/).

![](https://cdn.rawgit.com/manahl/pytest-plugins/master/pytest-profiling/docs/static/profile_combined.svg)


## Installation

Install using your favourite package installer:
```bash
    pip install pytest-profiling
    # or
    easy_install pytest-profiling
```

Enable the fixture explicitly in your tests or conftest.py (not required when using setuptools entry points):

```python
    pytest_plugins = ['pytest_profiling']
```

## Usage

Once installed, the plugin provides extra options to pytest:

```bash
    $ py.test --help
    ...
      Profiling:
        --profile           generate profiling information
        --profile-svg       generate profiling graph (using gprof2dot and dot
                            -Tsvg)
```

The ``--profile`` and ``profile-svg`` options can be combined with any other option:


```bash
    $ py.test tests/unit/test_logging.py --profile
    ============================= test session starts ==============================
    platform linux2 -- Python 2.6.2 -- pytest-2.2.3
    collected 3 items

    tests/unit/test_logging.py ...
    Profiling (from prof/combined.prof):
    Fri Oct 26 11:05:00 2012    prof/combined.prof

             289 function calls (278 primitive calls) in 0.001 CPU seconds

       Ordered by: cumulative time
       List reduced from 61 to 20 due to restriction <20>

       ncalls  tottime  percall  cumtime  percall filename:lineno(function)
            3    0.000    0.000    0.001    0.000 <string>:1(<module>)
          6/3    0.000    0.000    0.001    0.000 core.py:344(execute)
            3    0.000    0.000    0.001    0.000 python.py:63(pytest_pyfunc_call)
            1    0.000    0.000    0.001    0.001 test_logging.py:34(test_flushing)
            1    0.000    0.000    0.000    0.000 _startup.py:23(_flush)
            2    0.000    0.000    0.000    0.000 mock.py:979(__call__)
            2    0.000    0.000    0.000    0.000 mock.py:986(_mock_call)
            4    0.000    0.000    0.000    0.000 mock.py:923(_get_child_mock)
            6    0.000    0.000    0.000    0.000 mock.py:512(__new__)
            2    0.000    0.000    0.000    0.000 mock.py:601(__get_return_value)
            4    0.000    0.000    0.000    0.000 mock.py:695(__getattr__)
            6    0.000    0.000    0.000    0.000 mock.py:961(__init__)
        22/14    0.000    0.000    0.000    0.000 mock.py:794(__setattr__)
            6    0.000    0.000    0.000    0.000 core.py:356(getkwargs)
            6    0.000    0.000    0.000    0.000 mock.py:521(__init__)
            3    0.000    0.000    0.000    0.000 skipping.py:122(pytest_pyfunc_call)
            6    0.000    0.000    0.000    0.000 core.py:366(varnames)
            3    0.000    0.000    0.000    0.000 skipping.py:125(check_xfail_no_run)
            2    0.000    0.000    0.000    0.000 mock.py:866(assert_called_once_with)
            6    0.000    0.000    0.000    0.000 mock.py:645(__set_side_effect)


    =========================== 3 passed in 0.13 seconds ===========================
```

`pstats` files (one per test item) are retained for later analysis in `prof` directory, along with a `combined.prof` file:

```bash
    $ ls -1 prof/
    combined.prof
    test_app.prof
    test_flushing.prof
    test_import.prof
```

By default the `pstats` files are named after their corresponding test name, with illegal filesystem characters replaced by underscores.
If the full path is longer that operating system allows then it will be renamed to first 4 bytes of an md5 hash of the test name:

```bash
    $ ls -1 prof/
    combined.prof
    test_not_longer_than_max_allowed.prof
    68b329da.prof
```

If the ``--profile-svg`` option is given, along with the prof files and tabular output a svg file will be generated:

```bash
    $ py.test tests/unit/test_logging.py --profile-svg
    ...
    SVG profile in prof/combined.svg.
```

This is best viewed with a good svg viewer e.g. Chrome.

A number of [gprof2dot](https://github.com/jrfonseca/gprof2dot) options can be provided by either command line options to pytest or in any of the pytest ini
files. Any option that has a name with the _gprof2dot__ prefix is conveyed to gprof2dot after removing that prefix.
Because this plugin uses the gprof2dot _-f pstats_ option, at this time only the following
gprof2dot options are passed through by this plugin:
- \-\-gprof2dot-node-thres
- \-\-gprof2dot-edge-thres
- \-\-gprof2dot-skew
- \-\-gprof2dot-colormap
- \-\-gprof2dot-root
- \-\-gprof2dot-leaf

Note that if a function name is provided to either the --root or --leaf options and this
function symbol is not found in the combined.prof file, gprof2dot will
pipe an empty stream to dot.

### Plugin Options Affecting pstats.Stats

The analysis of the profiling data is done via usage of the
[profile.Stats](https://docs.python.org/3/library/profile.html#the-stats-class) class.
This usage can be configured via a couple of config properties specified either
on the pytest command line or via the usual ini/cfg config files.

- --profiling-sort-key 1 or more instances of this option will result in the values making up
an ordered list of sort keys being provided to the Stats.sort_stats() method. In the ini
configuration, specify the list via a "linelist" property. The default is "cumulative".
- --profiling-rev-order This option causes the ordering of the resulting Stats list specified sort keys to be
reversed, based on the sort keys specified.
- --profiling-filter - 1 or more of this option builds up a ordered list of _restrictions_ as defined in the
description of the [Stats.print_stats()](https://docs.python.org/3/library/profile.html#pstats.Stats.print_stats) method.
Note that the values provided to the --profiling-filter option will be converted to a float or
int or str for usage as documented.

Note that if the ordered list of restrictions result in an empty set of records to be
printed, this should not affect any SVG generation as that process is somewhat independent
of the stdout listing (the restrictions, sort, etc. are not utilized by the SVG generation)

### Issues

As of 2022-03-22, the use of the pytest-virtualenv plugin by the integration tests
requires a bit of a hack when using setuptools>=52.0.0. The lack of easy_install
means I chanced the virtualenv setup function to use pip as the installer. This
required the hack by which the pkg_name argument to VirtualEnv.install_package is
prefixed by the install command (for pip) and potentially followed by any version
specifiers (be sure these are in single quotes as the constructed command is eventually
used by Workspace.run() and is passed to the platform's shell - so metachars like > will be
used by the shell & not passed through to the Python code dealing with pip version
specifiers). This means that pkg_name values that won't match an installed (develop mode)
package will be installed by pip install. This breaks the copy of the integration test
files - copying this tree prior to running pytest will enable the tests to succeed.

How to do this in a CI/CD pipeline? Without including these in the wheel? (test only files)
