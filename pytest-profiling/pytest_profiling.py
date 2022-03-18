"""pytest: avoid already-imported warning: PYTEST_DONT_REWRITE."""
from __future__ import absolute_import

import sys
import os
import cProfile
import pstats
import errno
from hashlib import md5
from subprocess import Popen, PIPE

import six
import pytest

LARGE_FILENAME_HASH_LEN = 8


def clean_filename(s):
    forbidden_chars = set(r'/?<>\:*|"')
    return six.text_type("".join(c if c not in forbidden_chars and ord(c) < 127 else '_'
                                 for c in s))

def get_gprof2dot_options(config) -> [str] :
    # chop off the config property prefix
    prefix = 'gprof2dot_'
    arg = '--' + prefix[:len(prefix)-1] + '-'
    d : dict = { x: config.inicfg[x] for x in config.inicfg if x.startswith(prefix) }
    for a in config.invocation_params.args:   # command properties
        if a.startswith(arg):  # have to specify CLI form
            # ugh - no iterable list of CLI provided config property names so...
            pos = a.find('=')
            pos = len(a) if pos == -1 else pos
            k = a[:pos].replace('--','').replace('-','_') # convert to addoption formatted prop name
            val = config.getvalue(k)
            d[k] = val
    # not ideal, but all of the gprof2dot options use hyphens, no underscores so we get away with this.
    r: [] = ['--' + x[len(prefix):].replace('_', '-')+ \
             ('' if d[x] is None else '=' + d[x].strip()) \
             for x in d if x.startswith(prefix)]
    return r

def get_restriction_value(s) -> str or int or float :
    r = None
    try:
       r = int(s)
    except ValueError:
        try:
            r = float(s)
        except ValueError:
            r = s
    return r


class Profiling(object):
    """Profiling plugin for pytest."""
    svg = False
    svg_name = None
    profs = []
    stripdirs = False
    combined = None
    svg_err = None
    dot_cmd = None
    # reasonable defaults if we don't use the Config reference - match up with what addini specifies
    gprof2dot_cmd = None
    sort_keys = ['cumulative']
    rev_order = False
    restrictions = []
    gprof2dot_options = []
    profiling_mode = 'stats'

    def __init__(self, svg: bool, dir=None, element_number=20, stripdirs=False, config: pytest.Config = None):
        self.svg = svg
        self.dir = 'prof' if dir is None else dir[0]  # because of nargs=1 below
        self.stripdirs = stripdirs
        self.element_number = element_number
        self.profs = []
        self.gprof2dot = os.path.abspath(os.path.join(os.path.dirname(sys.executable), 'gprof2dot'))
        if not os.path.isfile(self.gprof2dot):
            # Can't see gprof in the local bin dir, we'll just have to hope it's on the path somewhere
            self.gprof2dot = 'gprof2dot'
        if config is not None:
            sort_keys = config.getvalue('profiling_sort_key')
            sort_keys = config.getini('profiling_sort_key') if sort_keys is None else sort_keys
            self.sort_keys = sort_keys if sort_keys is not None else self.sort_keys
            val = config.getvalue('profiling_rev_order')
            val = config.getini('profiling_rev_order') if val is None else val
            self.rev_order = val if val is not None else self.rev_order
            val = config.getvalue('profiling_filter')
            restrictions = config.getini('profiling_filter') if val is None else val
            restrictions = self.restrictions if restrictions is None else restrictions
            self.restrictions = [ get_restriction_value(s) for s in restrictions ]
            self.gprof2dot_options = get_gprof2dot_options(config)
            mode = config.getvalue('profiling_mode')
            mode = config.getini('profiling_mode') if mode is None else mode
            self.profiling_mode = mode if mode is not None else self.profiling_mode

    def pytest_sessionstart(self, session):  # @UnusedVariable
        try:
            os.makedirs(self.dir)
        except OSError:
            pass

    def pytest_sessionfinish(self, session, exitstatus):  # @UnusedVariable
        if self.profs:
            combined = pstats.Stats(self.profs[0])
            for prof in self.profs[1:]:
                combined.add(prof)
            self.combined = os.path.abspath(os.path.join(self.dir, "combined.prof"))
            combined.dump_stats(self.combined)
            if self.svg:
                self.svg_name = os.path.abspath(os.path.join(self.dir, "combined.svg"))

                # convert file <self.combined> into file <self.svg_name> using a pipe of gprof2dot | dot
                # gprof2dot -f pstats prof/combined.prof | dot -Tsvg -o prof/combined.svg

                # the 2 commands that we wish to execute
                gprof2dot_args = [sys.executable, '-m', 'gprof2dot', "-f", "pstats",
                                  *self.gprof2dot_options, self.combined]
                dot_args = ["dot", "-Tsvg", "-o", self.svg_name]
                self.dot_cmd = " ".join(dot_args)
                self.gprof2dot_cmd = " ".join(gprof2dot_args)

                # A handcrafted Popen pipe actually seems to work on both windows and unix:
                # do it in 2 subprocesses, with a pipe in between
                pdot = Popen(dot_args, stdin=PIPE, shell=False)  #  dot is not a shell script, even if it were
                pgprof = Popen(gprof2dot_args, stdout=pdot.stdin, shell=False) # no shell as we are using sys.executable
                (stdoutdata1, stderrdata1) = pgprof.communicate()
                (stdoutdata2, stderrdata2) = pdot.communicate()
                if stderrdata1 is not None or pgprof.poll() > 0:
                    # error: gprof2dot
                    self.svg_err = 1
                elif stderrdata2 is not None or pdot.poll() > 0:
                    # error: dot
                    self.svg_err = 2
                else:
                    # success
                    self.svg_err = 0

    def pytest_terminal_summary(self, terminalreporter):
        if self.combined:
            terminalreporter.write("Profiling (from {prof}):\n".format(prof=self.combined))
            stats = pstats.Stats(self.combined, stream=terminalreporter)
            if self.stripdirs:
              stats.strip_dirs()
            if self.rev_order:
                stats = stats.reverse_order()
            restrictions = self.restrictions
            if restrictions is None:
                restrictions = []
            if self.element_number is not None:
                restrictions.append( self.element_number )
            if self.profiling_mode == 'callers':
                stats.sort_stats(*self.sort_keys).print_callees(*restrictions)
            elif self.profiling_mode == 'callees':
                stats.sort_stats(*self.sort_keys).print_callers(*restrictions)
            else:
                stats.sort_stats(*self.sort_keys).print_stats(*restrictions)
        if self.svg_name:
            if not self.svg_err:
                # 0 - SUCCESS
                terminalreporter.write("SVG profile created in {svg}.\n".format(svg=self.svg_name))
            else:
                if self.svg_err == 1:
                    # 1 - GPROF2DOT ERROR
                    terminalreporter.write("Error creating SVG profile in {svg}.\n"
                                           "Command failed: {cmd}".format(svg=self.svg_name, cmd=self.gprof2dot_cmd))
                elif self.svg_err == 2:
                    # 2 - DOT ERROR
                    terminalreporter.write("Error creating SVG profile in {svg}.\n"
                                           "Command succeeded: {cmd} \n"
                                           "Command failed: {cmd2}".format(svg=self.svg_name, cmd=self.gprof2dot_cmd,
                                                                           cmd2=self.dot_cmd))

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        prof_filename = os.path.abspath(os.path.join(self.dir, clean_filename(item.name) + ".prof"))
        try:
            os.makedirs(os.path.dirname(prof_filename))
        except OSError:
            pass
        prof = cProfile.Profile()
        prof.enable()
        yield
        prof.disable()
        try:
            prof.dump_stats(prof_filename)
        except EnvironmentError as err:
            if err.errno != errno.ENAMETOOLONG:
                raise

            if len(item.name) < LARGE_FILENAME_HASH_LEN:
                raise

            hash_str = md5(item.name.encode('utf-8')).hexdigest()[:LARGE_FILENAME_HASH_LEN]
            prof_filename = os.path.join(self.dir, hash_str + ".prof")
            prof.dump_stats(prof_filename)
        self.profs.append(prof_filename)

def pytest_addoption(parser):
    """pytest_addoption hook for profiling plugin"""
    group = parser.getgroup('Profiling')
    group.addoption("--profile", action="store_true",
                    help="generate profiling information")
    group.addoption("--profile-svg", action="store_true",
                    help="generate profiling graph (using gprof2dot and dot -Tsvg)")
    group.addoption("--pstats-dir", nargs=1,  # if none provided, empty list returned?
                    help="configure the dump directory of profile data files")
    group.addoption("--element-number", action="store", type="int", default=20,
                    help="defines how many elements will display in a result")
    group.addoption("--strip-dirs", action="store_true", default=None,
                    help="configure to show/hide the leading path information "
                    "from file names")
    parser.addini("strip_dirs", help="configure to show/hide the leading path information "
                    "from file names", type="bool", default=False)
    # Stats.print_stats(), restriction args for use by pstats methods when doing terminal print
    #   multiple entries (multi-line ini or > 1 CLI arg
    group.addoption("--profiling-mode", type=str, choices=['stats', 'callers', 'callees'],default=None,
                    help="which Stats.print_? function to use")
    parser.addini("profiling_mode", help="which Stats.print_? function to use", default='stats')
    group.addoption("--profiling-sort-key", action="append", type=str,
                    choices=['cumulative', 'calls', 'cumtime', 'file',
                             'filename', 'module', 'ncalls', 'pcalls',
                             'line', 'name', 'nfl', 'stdname', 'time',
                             'tottime'],
                    default=None, help="ordered list of keys " # None because our ini has our default
                    "provided to pstats.sort_stats method")
    parser.addini("profiling_sort_key", help="ordered list of keys provided to pstats.sort_stats method",
                  type="linelist", default=["cumulative"])
    group.addoption("--profiling-rev-order", action="store_true",
                    default=None,  # if no command line, as our ini has a default
                    help="if specified, pstats.reverse_order() utilized")
    parser.addini("profiling_rev_order", help="if specified, pstats.reverse_order() utilized",
                  type="bool", default=False)
    # these are the restrictions that various pstats methods can utilize
    # no point using a custom type conversion function as the pstats restrictions can be strings, ints, floats here
    # as there isn't one for the addini(), we will use it when we grab the values.
    group.addoption("--profiling-filter", action="append", type=str, default=None, help="pstats restriction values")
    parser.addini("profiling_filter", help="pstats restriction values", type="linelist", default=[])

    # new grprof2dot options - as we are passing these through to the gprof2dot command, we treat all such
    # options as strings - let gprof2dot parse as needed.
    # if there are any options that do not take a value (ie. the presence of the option itself is a bool) you MUST
    # specify the default as None so the correct format is conveyed to the generated command line
    group.addoption("--gprof2dot-node-thres", action="store", type=float,
                     default=None, help="eliminate nodes below this threshold")
    parser.addini("gprof2dot_node_thres", help="eliminate nodes below this "
                  "threshold", type="string", default="0.5")
    group.addoption("--gprof2dot-edge-thres", action="store", type=float,
                    default=None, help="eliminate edges below this threshold")
    parser.addini("gprof2dot_edge_thres", help="eliminate edges below this threshold", type="string", default="0.1")
    group.addoption("--gprof2dot-skew", action="store", type=float,
                    default=None, help="skew the colorization curve.  Values "
                    "< 1.0 give more\nvariety to lower percentages.  Values "
                    "> 1.0 give less\nvariety to lower percentages")
    parser.addini("gprof2dot_skew", help="skew the colorization curve.  Values "
                 "< 1.0 give more\nvariety to lower percentages.  Values "
                 "> 1.0 give less\nvariety to lower percentages",
                 type="string", default="1.0" )
    group.addoption("--gprof2dot-colormap", action="store", type=str, default=None,
                    choices=['color', 'pink', 'gray', 'bw', 'print'],
                    help="color map: color, pink, gray, bw, or print")
    parser.addini("gprof2dot_colormap", help="color map: color, pink, gray, bw, or print", type="string",
                  default="color")
    group.addoption("--gprof2dot-root", action="store", type=str, default=None,
                    help="prune call graph to show only descendants of specified root function")
    parser.addini("gprof2dot_root", help="prune call graph to show only descendants of specified root function",
                  type="string", default=None)
    group.addoption("--gprof2dot-leaf", action="store", type=str, default=None,
                    help="prune call graph to show only ancestors of specified leaf function")
    parser.addini("gprof2dot_leaf", help="prune call graph to show only ancestors of specified leaf function",
                  type="string", default=None)


def pytest_configure(config):
    """pytest_configure hook for profiling plugin"""
    profile_enable = any(config.getvalue(x) for x in ('profile', 'profile_svg'))
    if profile_enable:
        val = config.getvalue('strip_dirs')
        stripdirs = config.getini('strip_dirs') if val is None else val
        stripdirs = False if stripdirs is None else stripdirs
        config.pluginmanager.register(Profiling(config.getvalue('profile_svg'),
                                                config.getvalue('pstats_dir'),
                                                element_number=config.getvalue('element_number'),
                                                stripdirs=stripdirs,
                                                config=config))


