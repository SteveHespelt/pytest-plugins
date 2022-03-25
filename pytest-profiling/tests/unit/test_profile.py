# HACK: if the profile plugin is imported before the coverage plugin then all
# the top-level code in pytest_profiling will be omitted from
# coverage, so force it to be reloaded within this test unit under coverage

from six.moves import reload_module  # @UnresolvedImport

import pytest_profiling
reload_module(pytest_profiling)

from pytest_profiling import Profiling, pytest_addoption, pytest_configure, get_gprof2dot_options, \
    get_restriction_value

try:
    from unittest.mock import Mock, ANY, patch, sentinel
except ImportError:
    # python 2
    from mock import Mock, ANY, patch, sentinel


def test_creates_prof_dir():
    with patch('os.makedirs', side_effect=OSError) as makedirs:
        Profiling(False).pytest_sessionstart(Mock())
    makedirs.assert_called_with('prof')


def test_combines_profs():
    plugin = Profiling(False)
    plugin.profs = [sentinel.prof0, sentinel.prof1]
    with patch('pstats.Stats') as Stats:
        plugin.pytest_sessionfinish(Mock(), Mock())
    Stats.assert_called_once_with(sentinel.prof0)
    Stats.return_value.add.assert_called_once_with(sentinel.prof1)
    assert Stats.return_value.dump_stats.called


def test_generates_svg():
    """ we're not testing that gprof2dot actually worked, just that it was going to be called by Popen.communicate().
    Integration tests are for checking if full functionality with integrated components (eg. gprof2dot) actually work.
    """
    plugin = Profiling(True)
    plugin.profs = [sentinel.prof]
    with patch('pstats.Stats'):
        plugin.pytest_sessionfinish(Mock(), Mock())
    assert '-m gprof2dot' in plugin.gprof2dot_cmd
    assert plugin.svg_name is not None
    #assert any('gprof2dot' in args[0][0] for args in Template.return_value.append.call_args_list)
    #assert Template.return_value.copy.called
    # if we want to check, we can use: assert plugin.svg_err == 0


def test_writes_summary():
    plugin = Profiling(False)
    plugin.profs = [sentinel.prof]
    terminalreporter, stats = Mock(), Mock()
    with patch('pstats.Stats', return_value=stats) as Stats:
        plugin.pytest_sessionfinish(Mock(), Mock())
        plugin.pytest_terminal_summary(terminalreporter)
    assert 'Profiling' in terminalreporter.write.call_args[0][0]
    assert Stats.called_with(stats, stream=terminalreporter)


def test_writes_summary_svg():
    plugin = Profiling(True)
    plugin.profs = [sentinel.prof]
    terminalreporter = Mock()
    with patch('pstats.Stats'):
        plugin.pytest_sessionfinish(Mock(), Mock())
        plugin.pytest_terminal_summary(terminalreporter)
    assert 'SVG' in terminalreporter.write.call_args[0][0]


def test_adds_options():
    parser = Mock()
    pytest_addoption(parser)
    parser.getgroup.assert_called_with('Profiling')
    group = parser.getgroup.return_value
    group.addoption.assert_any_call('--profile', action='store_true', help=ANY)
    group.addoption.assert_any_call('--profile-svg', action='store_true', help=ANY)


def test_configures():
    config = Mock(getvalue=lambda x: x == 'profile')
    with patch('pytest_profiling.Profiling') as Profiling:
        pytest_configure(config)
    config.pluginmanager.register.assert_called_with(Profiling.return_value)


def test_clean_filename():
    assert pytest_profiling.clean_filename('a:b/c\256d') == 'a_b_c_d'


def test_get_gprof2dot_options_cli():
    config = Mock()
    config.inicfg = {}  # only passing config properties via CLI
    config.invocation_params.args = ['--gprof2dot-leaf=the_leaf_function','--other-property=val1']
    config.getvalue.return_value = 'the_leaf_function'
    r = get_gprof2dot_options(config)
    assert len(r) == 1
    assert r[0] == '--leaf=the_leaf_function'


def test_get_gprof2dot_options_cli2():
    """ Test involving CLI options with no value (bool state) """
    config = Mock()
    config.inicfg = {}  # only passing config properties via CLI
    config.invocation_params.args = ['--gprof2dot-use-it', '--other-property=val1']
    config.getvalue.return_value = None
    r = get_gprof2dot_options(config)
    assert len(r) == 1
    assert r[0] == '--use-it'


def test_get_gprof2dot_options_cli3():
    """ Test involving CLI options with mix of properties with no value (bool state) and with a value """
    config = Mock()
    config.inicfg = {}  # only passing config properties via CLI
    config.invocation_params.args = ['--gprof2dot-use-it', '--other-property=val1', '--gprof2dot-root=root_func']
    config.getvalue = lambda s: {'gprof2dot_root':'root_func', 'gprof2dot_use_it':None}.get(s, None)
    r = get_gprof2dot_options(config)
    assert len(r) == 2
    assert r[0] == '--use-it'
    assert r[1] == '--root=root_func'


def test_get_gprof2dot_options_ini():
    config = Mock()
    config.inicfg = {'gprof2dot_root': 'the_root_func', 'not_gprof2dot_leaf': 'a_leaf_function'}
    config.invocation_params.args = {}
    config.getvalue.return_value = 'Should not be utilized'  # because we are not using CLI provided config props
    r = get_gprof2dot_options(config)
    assert len(r) == 1
    assert r[0] == '--root=the_root_func'


def test_get_restriction_value():
    i = get_restriction_value('45')
    assert isinstance(i, int)
    assert i == 45
    f = get_restriction_value('11.23')
    assert isinstance(f, float)
    assert 11.22 < f < 11.24
    assert f == 11.23
    inp: str = '12 a string value 23.4'
    s = get_restriction_value(inp)
    assert isinstance(s, str)
    assert s == inp


# some simple tests to confirm that config properties are conveyed to the Profiling object correctly (not verifing
# the usage of these, that's later

def test_cli_configs_set():
    config = Mock()
    config.inicfg = {}  # only passing config properties via CLI
    config.invocation_params.args = ['--gprof2dot-use-it', '--other-property=val1', '--gprof2dot-root=root_func']
    # totally based on the args list, and what the addoptions or addini defaults are
    config.getvalue = lambda s: 'root_func' if s == 'gprof2dot_root' else 'stats' if s == 'profiling_mode' else None
    config.getini = lambda s: { 'profiling_sort_key': ['cumulative']}.get(s, None)
    profiling = Profiling( False, dir=None, config=config )
    assert profiling.profiling_mode == 'stats'
    assert len(profiling.sort_keys) == 1
    assert profiling.sort_keys[0] == 'cumulative'
    assert profiling.gprof2dot_options == ['--use-it', '--root=root_func']


def test_cli_configs_set2():
    config = Mock()
    config.inicfg = {}  # only passing config properties via CLI
    config.invocation_params.args = ['--other-property=val1', '--profiling-mode=callers']
    # totally based on the args list, and what the addoptions or addini defaults are
    config.getvalue = lambda s: { 'gprof2dot_root': 'root_func', 'profiling_mode': 'callers'}.get(s, None)
    config.getini = lambda s: { 'profiling_sort_key': ['ncalls','cumulative']}.get(s, None)
    profiling = Profiling( False, dir=None, config=config )
    assert profiling.profiling_mode == 'callers'
    assert len(profiling.sort_keys) == 2
    assert profiling.sort_keys[0] == 'ncalls'
    assert profiling.sort_keys[1] == 'cumulative'
    assert profiling.gprof2dot_options == []


