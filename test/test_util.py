# /test/test_util.py
#
# Test cases for the bootstrap script.
#
# See /LICENCE.md for Copyright information
"""Test cases for the util script."""

import copy

import doctest

import os

import platform

import shutil

import subprocess

import tempfile

from tempfile import mkdtemp

from ciscripts.bootstrap import (BashParentEnvironment,
                                 escaped_printer)
import ciscripts.util as util

from mock import Mock

from testtools import TestCase
from testtools.matchers import (Contains,
                                DocTestMatches,
                                Equals,
                                MatchesAll,
                                MatchesAny,
                                Not)

import testutil


class TestPrintMessage(TestCase):

    """Test cases for util.print_message."""

    def test_no_print_to_stdout(self):
        """Test that messages printed to stderr have leading newline."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            util.print_message("hello")

        self.assertEqual(captured_output.stdout, str())


class OverwrittenEnvironmentVarsTestCase(TestCase):

    """Base class for TestCase where environment variables are overwritten."""

    def __init__(self, *args, **kwargs):
        """Initialize this base class and set instance variables."""
        super(OverwrittenEnvironmentVarsTestCase, self).__init__(*args,
                                                                 **kwargs)
        self._saved_environ = None

    def setUp(self):  # suppress(N802)
        """Set up this test case by saving the current environment."""
        super(OverwrittenEnvironmentVarsTestCase, self).setUp()
        self._saved_environ = copy.deepcopy(os.environ)

    def tearDown(self):  # suppress(N802)
        """Tear down this test case by restoring the saved environment."""
        os.environ = copy.deepcopy(self._saved_environ)
        super(OverwrittenEnvironmentVarsTestCase, self).tearDown()


class TestOverwriteEnvironmentVariables(OverwrittenEnvironmentVarsTestCase):

    """Test case for util.overwrite_environment_variable."""

    def __init__(self, *args, **kwargs):
        """Initialize instance variables, including parent environment."""
        super(TestOverwriteEnvironmentVariables, self).__init__(*args,
                                                                **kwargs)
        self._parent = BashParentEnvironment(escaped_printer)

    def _get_parent_env_value(self, env_script, var):
        """Evaluate env_script and return value of variable in a shell."""
        return subprocess.check_output(["bash",
                                        "-c",
                                        (env_script +
                                         (" echo \"${%s}\"" % var))]).strip()

    def test_overwritten_environment_variables_in_os_environ(self):
        """Test that overwritten environment variables are in os.environ."""
        with testutil.CapturedOutput():
            util.overwrite_environment_variable(self._parent, "VAR", "VALUE")

        self.assertThat(os.environ, Contains("VAR"))
        self.assertEqual(os.environ["VAR"], "VALUE")

    def test_overwritten_environment_variables_evaluated(self):
        """Test that overwritten environment variables are in os.environ."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            util.overwrite_environment_variable(self._parent, "VAR", "VALUE")

        self.assertEqual(captured_output.stdout, "export VAR=\"VALUE\";\n")

    def test_prepended_environment_variables_in_os_environ_list(self):
        """Prepended environment variables appear in the semicolon list."""
        with testutil.CapturedOutput():
            util.prepend_environment_variable(self._parent, "VAR", "VALUE")
            util.prepend_environment_variable(self._parent,
                                              "VAR",
                                              "SECOND_VALUE")

        self.assertThat(os.environ["VAR"].split(":"),
                        MatchesAll(Contains("VALUE"),
                                   Contains("SECOND_VALUE")))

    def test_prepended_environment_variables_in_parent(self):
        """Prepended variables appear in parent shell environment."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            util.overwrite_environment_variable(self._parent, "VAR", "VALUE")
            util.prepend_environment_variable(self._parent,
                                              "VAR",
                                              "SECOND_VALUE")

        parent_env_value = self._get_parent_env_value(captured_output.stdout,
                                                      "VAR")
        self.assertThat(parent_env_value.split(":"),
                        MatchesAll(Contains("VALUE"),
                                   Contains("SECOND_VALUE")))

    def test_unset_environment_variable_in_os_environ(self):
        """Environment overwritten with None unset in os.environ."""
        with testutil.CapturedOutput():
            util.overwrite_environment_variable(self._parent, "VAR", "VALUE")
            util.overwrite_environment_variable(self._parent, "VAR", None)

        self.assertThat(os.environ, Not(Contains("VAR")))

    def test_unset_environment_variable_in_parent(self):
        """Environment overwritten with None unset in parent."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            util.overwrite_environment_variable(self._parent, "VAR", "VALUE")
            util.overwrite_environment_variable(self._parent, "VAR", None)

        parent_env_value = self._get_parent_env_value(captured_output.stdout,
                                                      "VAR")
        self.assertEqual(parent_env_value.strip(), "")

    def test_remove_value_from_environment_variable_in_os_environ(self):
        """Remove a value from a colon separated value list in os.environ."""
        with testutil.CapturedOutput():
            util.overwrite_environment_variable(self._parent, "VAR", "VALUE")
            util.prepend_environment_variable(self._parent,
                                              "VAR",
                                              "SECOND_VALUE")
            util.remove_from_environment_variable(self._parent, "VAR", "VALUE")

        self.assertThat(os.environ["VAR"].split(":"),
                        MatchesAll(Not(Contains("VALUE")),
                                   Contains("SECOND_VALUE")))

    def test_remove_value_from_environment_variable_in_parent(self):
        """Remove a value from a colon separated value list in parent shell."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            util.overwrite_environment_variable(self._parent, "VAR", "VALUE")
            util.prepend_environment_variable(self._parent,
                                              "VAR",
                                              "SECOND_VALUE")
            util.remove_from_environment_variable(self._parent, "VAR", "VALUE")

        parent_env_value = self._get_parent_env_value(captured_output.stdout,
                                                      "VAR")
        self.assertThat(parent_env_value.split(":"),
                        MatchesAll(Not(Contains("VALUE")),
                                   Contains("SECOND_VALUE")))


class TestTask(TestCase):

    """Test case for util.Task."""

    def test_description_after_fat_arrow_first_level(self):
        """Description printed after fat arrow on first level."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            with util.Task("Description"):
                pass

        self.assertEqual(captured_output.stderr, "\n==> Description")

    def test_description_after_dots_second_level(self):
        """Description printed after dots on first level."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            with util.Task("Description"):
                with util.Task("Secondary Description"):
                    pass

        self.assertEqual("\n==> Description"
                         "\n    ... Secondary Description\n",
                         captured_output.stderr)

    def test_nest_to_thrid_level(self):
        """Nest to third level with dots."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            with util.Task("Description"):
                with util.Task("Secondary Description"):
                    with util.Task("Tertiary Description"):
                        pass

        self.assertEqual("\n==> Description"
                         "\n    ... Secondary Description"
                         "\n        ... Tertiary Description\n",
                         captured_output.stderr)

    def output_is_on_level_after_task_description(self):
        """Command output gets printed to level after task description."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            with util.Task("Description"):
                util.IndentedLogger().message("command_output\n"
                                              "command_output\n")

        self.assertEqual(captured_output.stderr,
                         "\n==> Description"
                         "\n    command_output"
                         "\n    command_output"
                         "\n")


class TestExecute(TestCase):

    """Test case for util.execute."""

    def test_execute_with_success(self):
        """Execute a command with success."""
        self.assertEqual(0, util.execute(Mock(), util.output_on_fail, "true"))

    def test_execute_with_failure(self):
        """Execute a command with failure."""
        with testutil.CapturedOutput():
            self.assertEqual(1,
                             util.execute(Mock(),
                                          util.output_on_fail,
                                          "false"))

    def test_instant_failure_calls_through_to_container(self):
        """Execute a command with failure."""
        container = Mock()
        with testutil.CapturedOutput():
            util.execute(container, util.output_on_fail, "false")

        container.note_failure.assert_called()  # suppress(PYC70)

    def test_execute_with_failure_output(self):
        """Execute a command with failure, showing output."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            util.execute(Mock(),
                         util.output_on_fail,
                         "python",
                         "/does-not-exist")

        self.assertThat(captured_output.stderr,
                        DocTestMatches("python: can't open file"
                                       " '/does-not-exist': ... "
                                       "!!! Process python /does-not-exist "
                                       "failed with 2",
                                       doctest.ELLIPSIS |
                                       doctest.NORMALIZE_WHITESPACE |
                                       doctest.REPORT_NDIFF))

    def test_execute_with_success_running_output(self):
        """Execute a command with success, but show output."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            util.execute(Mock(), util.running_output, "python", "--version")

        self.assertThat(captured_output.stderr,
                        DocTestMatches("\nPython ...",
                                       doctest.ELLIPSIS |
                                       doctest.NORMALIZE_WHITESPACE))

    def test_running_output_no_double_leading_slash_n(self):
        """Using running_output does not allow double-leading slash-n."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            util.execute(Mock(),
                         util.running_output,
                         "python",
                         "-c",
                         "print(\"\")")

        self.assertThat(captured_output.stderr,
                        DocTestMatches("\n",
                                       doctest.ELLIPSIS |
                                       doctest.NORMALIZE_WHITESPACE))

    def test_execute_show_dots_for_long_running_processes(self):
        """Show dots for long running processes."""
        captured_output = testutil.CapturedOutput()
        with captured_output:
            util.execute(Mock(),
                         util.long_running_suppressed_output(dot_timeout=1),
                         "sleep", "3")

        # There will be fewer dots as the watcher thread start a little
        # later than the subprocess does. However, there can be some cases
        # where there's a little bit of lag between terminating threads, so
        # there might be three dots. Match both cases.
        self.assertThat(captured_output.stderr.strip(),
                        MatchesAny(Equals(".."),
                                   Equals("...")))


class TestExecutablePaths(TestCase):

    """Test cases for executable path functions (util.which)."""

    def __init__(self, *args, **kwargs):
        """Initialize this test case and its instance variables."""
        super(TestExecutablePaths, self).__init__(*args, **kwargs)
        self._saved_path = None

    def setUp(self):  # suppress(N802)
        """Keep a copy of os.environ["PATH"]."""
        super(TestExecutablePaths, self).setUp()
        self._saved_path = copy.deepcopy(os.environ.get("PATH"))

    def tearDown(self):  # suppress(N802)
        """Restore os.environ["PATH"]."""
        os.environ["PATH"] = copy.deepcopy(self._saved_path)
        super(TestExecutablePaths, self).tearDown()

    def test_find_executable_file_in_path(self):
        """Find an executable file in the current PATH."""
        with testutil.in_tempdir(os.getcwd(), "executable_path") as temp_dir:
            os.environ["PATH"] = (temp_dir +
                                  ":" +
                                  (os.environ.get("PATH") or ""))

            with tempfile.NamedTemporaryFile(dir=temp_dir) as temp_file:
                temp_file.write("#!/usr/bin/env python\nprint(\"Test\")")
                os.chmod(temp_file.name, 755)

                self.assertEqual(temp_file.name,
                                 util.which(os.path.basename(temp_file.name)))

    def test_non_executable_file_not_found(self):
        """Don't find a non executable file in the current PATH."""
        with testutil.in_tempdir(os.getcwd(), "executable_path") as temp_dir:
            os.environ["PATH"] = (temp_dir +
                                  ":" +
                                  (os.environ.get("PATH") or ""))

            with tempfile.NamedTemporaryFile(dir=temp_dir) as temp_file:
                temp_file.write("#!/usr/bin/env python\nprint(\"Test\")")

                self.assertEqual(None,
                                 util.which(os.path.basename(temp_file.name)))

    def test_file_not_in_path_not_found(self):
        """Check that executables not in PATH are not found."""
        with testutil.in_tempdir(os.getcwd(), "executable_path") as temp_dir:
            with tempfile.NamedTemporaryFile(dir=temp_dir) as temp_file:
                temp_file.write("#!/usr/bin/env python\nprint(\"Test\")")
                os.chmod(temp_file.name, 755)

                self.assertEqual(None,
                                 util.which(os.path.basename(temp_file.name)))

    def test_symlinks_in_path_get_resolved(self):
        """Returned executable path has symlinks resolved."""
        with testutil.in_tempdir(os.getcwd(), "executable_path") as temp_dir:
            link = os.path.join(temp_dir, "link")
            linked = os.path.join(temp_dir, "linked")

            os.mkdir(linked)
            os.symlink(linked, link)

            path_var = (os.environ.get("PATH") or "")

            os.environ["PATH"] = link + ":" + path_var

            with tempfile.NamedTemporaryFile(dir=linked) as temp_file:
                temp_file.write("#!/usr/bin/env python\nprint(\"Test\")")
                os.chmod(temp_file.name, 755)

                self.assertEqual(temp_file.name,
                                 util.which(os.path.basename(temp_file.name)))

    def test_resolve_relative_paths(self):
        """Resolve relative paths in PATH."""
        with testutil.in_tempdir(os.getcwd(), "executable_path") as temp_dir:
            path_var = (os.environ.get("PATH") or "")
            base = os.path.basename(temp_dir)
            os.environ["PATH"] = "{0}/../{1}:{2}".format(temp_dir,
                                                         base,
                                                         path_var)

            with tempfile.NamedTemporaryFile(dir=temp_dir) as temp_file:
                temp_file.write("#!/usr/bin/env python\nprint(\"Test\")")
                os.chmod(temp_file.name, 755)

                self.assertEqual(temp_file.name,
                                 util.which(os.path.basename(temp_file.name)))

    def test_execute_function_if_not_found_by_which(self):
        """Execute function with where_unavailable if executable not found."""
        with testutil.in_tempdir(os.getcwd(), "executable_path") as temp_dir:
            with tempfile.NamedTemporaryFile(dir=temp_dir) as temp_file:
                temp_file.write("#!/usr/bin/env python\nprint(\"Test\")")
                os.chmod(temp_file.name, 755)

                mock = Mock()
                util.where_unavailable(os.path.basename(temp_file.name),
                                       mock,
                                       "arg")

                mock.assert_called_with("arg")

    def test_no_execute_function_if_found_by_which(self):
        """where_unavailable doesn't execute function if executable found."""
        with testutil.in_tempdir(os.getcwd(), "executable_path") as temp_dir:
            with tempfile.NamedTemporaryFile(dir=temp_dir) as temp_file:
                temp_file.write("#!/usr/bin/env python\nprint(\"Test\")")
                os.chmod(temp_file.name, 755)

                mock = Mock()
                util.where_unavailable(os.path.basename(temp_file.name),
                                       mock,
                                       "arg")
                mock.assert_not_called()  # suppress(PYC70)


class TestApplicationToFilePatterns(TestCase):

    """Test cases for apply_to_files/directories_matching."""

    def test_apply_to_matching_files_by_prefix(self):
        """Apply functions to files matching prefix."""
        with testutil.in_tempdir(os.getcwd(), "file_patterns") as temp_dir:
            with tempfile.NamedTemporaryFile(dir=temp_dir) as temp_file:
                temp_file.write("")
                temp_file.flush()

                function_applied = Mock()
                util.apply_to_files(function_applied,
                                    temp_dir,
                                    matching=["{0}/*".format(temp_dir)])

                function_applied.assert_called_with(temp_file.name)

    def test_apply_to_matching_files_by_suffix(self):
        """Apply functions to files matching suffix."""
        with testutil.in_tempdir(os.getcwd(), "file_patterns") as temp_dir:
            with tempfile.NamedTemporaryFile(dir=temp_dir,
                                             suffix=".tmp") as temp_file:
                temp_file.write("")
                temp_file.flush()

                function_applied = Mock()
                util.apply_to_files(function_applied,
                                    temp_dir,
                                    matching=["*.{0}".format("tmp")])

                function_applied.assert_called_with(temp_file.name)

    def test_no_apply_files_not_matching_suffix(self):
        """Don't apply functions to files not matching suffix."""
        with testutil.in_tempdir(os.getcwd(), "file_patterns") as temp_dir:
            with tempfile.NamedTemporaryFile(dir=temp_dir,
                                             suffix=".tmp") as temp_file:
                temp_file.write("")
                temp_file.flush()

                function_applied = Mock()
                util.apply_to_files(function_applied,
                                    temp_dir,
                                    matching=["*.{0}".format("other")])

                function_applied.assert_not_called()  # suppress(PYC70)

    def test_apply_to_directories_matching(self):
        """Apply functions to directories matching prefix."""
        with testutil.in_tempdir(os.getcwd(), "file_patterns") as temp_dir:
            with testutil.in_tempdir(os.getcwd(), "matched") as matched:
                base = os.path.basename(matched)
                function_applied = Mock()
                util.apply_to_directories(function_applied,
                                          temp_dir,
                                          matching=["*/{0}".format(base)])

                function_applied.assert_called_with(matched)

    def test_no_apply_to_directories_not_matching(self):
        """Don't apply to directories."""
        with testutil.in_tempdir(os.getcwd(), "file_patterns") as temp_dir:
            with testutil.in_tempdir(os.getcwd(), "matched"):
                function_applied = Mock()
                util.apply_to_directories(function_applied,
                                          temp_dir,
                                          matching=["{0}/*".format("other")])

                function_applied.assert_not_called()  # suppress(PYC70)


class TestGetSystemIdentifier(TestCase):

    """Test cases for the :get_system_identifier: function."""

    def __init__(self, *args, **kwargs):
        """Initialize this TestCase."""
        super(TestGetSystemIdentifier, self).__init__(*args, **kwargs)
        self._temporary_directory = None

    def setUp(self):  # suppress(N802)
        """Create a stub class with a temporary directory to store files in."""
        super(TestGetSystemIdentifier, self).setUp()

        class StubContainer(object):

            """A stub container with the named_cache_dir function defined."""

            def __init__(self, temporary_directory):
                """Initialize this StubContainer in temporary_directory."""
                super(StubContainer, self).__init__()
                self._temporary_directory = temporary_directory

            def named_cache_dir(self, directory):
                """Create a named cache directory."""
                cache_dir = os.path.join(self._temporary_directory, directory)
                try:
                    os.makedirs(cache_dir)
                except OSError:
                    pass

                return cache_dir

        self._temporary_directory = mkdtemp(prefix=os.path.join(os.getcwd(),
                                                                "sysid"))

        self.container = StubContainer(self._temporary_directory)

    def tearDown(self):  # suppress(N802)
        """Remove the temporary directory for this container."""
        shutil.rmtree(self._temporary_directory)
        super(TestGetSystemIdentifier, self).tearDown()

    def test_system_identifier_has_architecture(self):
        """Determined system identifier has architecture."""
        self.assertThat(util.get_system_identifier(self.container),
                        Contains(platform.machine()))

    def test_system_identifier_has_system_name(self):
        """Determined system identifier has OS name."""
        self.assertThat(util.get_system_identifier(self.container),
                        Contains(platform.system().lower()))