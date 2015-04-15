# /ciscripts/util.py
#
# General utility functions which are made available to all other scripts
#
# See /LICENCE.md for Copyright information
"""General utility functions which are made available to all other scripts."""

import fnmatch

import os

import select

import stat

import subprocess

import sys

import threading


from contextlib import contextmanager

try:
    from Queue import Queue
except ImportError:
    from queue import queue  # suppress(F811,E301,E101,F401)


def print_message(message):
    """Print to stderr."""
    sys.stderr.write("{0}".format(message))


def overwrite_environment_variable(parent, key, value):
    """Overwrite environment variables in current and parent context."""
    if value is not None:
        os.environ[key] = str(value)
    else:
        del os.environ[key]

    parent.overwrite_environment_variable(key, value)


def prepend_environment_variable(parent, key, value):
    """Prepend value to the environment variable list in key."""
    os.environ[key] = "{0}:{1}".format(str(value), os.environ.get(key) or "")
    parent.prepend_environment_variable(key, value)


def remove_from_environment_variable(parent, key, value):
    """Remove value from an environment variable list in key."""
    environ_list = maybe_environ(key).split(":")
    os.environ[key] = ":".join([i for i in environ_list if i != value])

    # See http://stackoverflow.com/questions/370047/
    parent.remove_from_environment_variable(key, value)


def define_command(parent, name, command):
    """Define a function called name which runs command in the parent scope."""
    parent.define_command(name, command)


def maybe_environ(key):
    """Return environment variable for key, or an empty string."""
    try:
        return os.environ[key]
    except KeyError:
        return ""


def _match_all(abs_dir, matching, not_matching):
    """Return all directories in abs_dirs matching all expressions."""
    for expression in matching:
        if not fnmatch.fnmatch(abs_dir, expression):
            return False

    for expression in not_matching:
        if fnmatch.fnmatch(abs_dir, expression):
            return False

    return True


def apply_to_files(func, tree_node, matching=[], not_matching=[]):
    """Apply recursively to all files in tree_node.

    Function will be applied to all filenames matching 'matching', but
    will not be applied to any file matching matching 'not_matching'.
    """
    result = []
    for root, _, filenames in os.walk(tree_node):
        abs_files = [os.path.join(root, f) for f in filenames]
        result.extend([func(f) for f in abs_files if _match_all(f,
                                                                matching,
                                                                not_matching)])

    return result


def apply_to_directories(func, tree_node, matching=[], not_matching=[]):
    """Apply recursively to all directories in tree_node.

    Function will be applied to all filenames matching 'matching', but
    will not be applied to any file matching matching 'not_matching'.
    """
    result = []
    for root, directories, _, in os.walk(tree_node):
        abs_dirs = [os.path.join(root, d) for d in directories]
        result.extend([func(d) for d in abs_dirs if _match_all(d,
                                                               matching,
                                                               not_matching)])

    return result


class IndentedLogger(object):

    """A logger that writes to sys.stderr with indents.

    IndentedLogger follows some rules when logging to ensure that
    output is formatted in the way that you expect.

    When it is used as a context manager, the indent level increases by one,
    and all subsequent output is logged on the next indentation level.

    The logger also ensures that initial and parting newlines are printed
    in the right place.
    """

    _indent_level = 0
    _printed_on_secondary_indents = False

    def __init__(self):
        """Initialize this IndentedLogger."""
        super(IndentedLogger, self).__init__()

    def __enter__(self):
        """Increase indent level and return self."""
        IndentedLogger._indent_level += 1
        return self

    def __exit__(self, exc_type, value, traceback):
        """Decrease indent level.

        If we printed anything whilst we were indented on more than level
        zero, then print a trailing newline, to separate out output sets.
        """
        del exc_type
        del value
        del traceback

        IndentedLogger._indent_level -= 1

        if (IndentedLogger._indent_level == 0 and
                IndentedLogger._printed_on_secondary_indents):
            sys.stderr.write("\n")
            IndentedLogger._printed_on_secondary_indents = False

    def message(self, message_to_print):
        """Print a message, with a pre-newline, splitting on newlines."""
        if IndentedLogger._indent_level > 0:
            IndentedLogger._printed_on_secondary_indents = True

        indent = IndentedLogger._indent_level * "    "
        formatted = message_to_print.replace("\r", "\r" + indent)
        formatted = formatted.replace("\n", "\n" + indent)
        print_message(formatted)

    def dot(self):
        """Print a dot, just for status."""
        sys.stderr.write(".")


class Task(object):

    """A message for a task to being performed.

    Use this as a context manager to print a message and then perform
    a task within that context. Nested tasks get nested indents.
    """

    nest_level = 0

    def __init__(self, description):
        """Initialize this Task."""
        super(Task, self).__init__()

        indicator = "==>" if Task.nest_level == 0 else "..."
        IndentedLogger().message("\n{0} {1}".format(indicator, description))

    def __enter__(self):
        """Increment active nesting level."""
        Task.nest_level += 1
        IndentedLogger().__enter__()

    def __exit__(self, exec_type, value, traceback):
        """Decrement the active nesting level."""
        IndentedLogger().__exit__(exec_type, value, traceback)
        Task.nest_level -= 1


@contextmanager
def thread_output(*args, **kwargs):
    """Get return value of thread as queue, joining on end."""
    return_queue = Queue()
    kwargs["args"] = (kwargs["args"] or tuple()) + (return_queue, )
    thread = threading.Thread(*args, **kwargs)
    thread.start()
    yield return_queue
    thread.join()


def output_on_fail(process, outputs):
    """Capture output, displaying it if the process fails."""
    def reader(handle, input_queue):
        """Thread which reads handle, until EOF."""
        input_queue.put(handle.read())

    with thread_output(target=reader, args=(outputs[0], )) as stdout_queue:
        with thread_output(target=reader,
                           args=(outputs[1], )) as stderr_queue:
            stdout = stdout_queue.get()
            stderr = stderr_queue.get()

    status = process.wait()

    if status != 0:
        logger = IndentedLogger()
        logger.message("\n")
        logger.message(stdout)
        logger.message(stderr)

    return status


def long_running_suppressed_output(dot_timeout=10):
    """Print dots in a separate thread until our process is done."""
    logger = IndentedLogger()

    def strategy(process, outputs):
        """Partially applied strategy to be passed to execute."""
        def print_dots(status_pipe):
            """Print a dot every dot_timeout seconds."""
            while True:
                # Exit when something gets written to the pipe
                read, _, _ = select.select([status_pipe], [], [], dot_timeout)

                if len(read) > 0:
                    return
                else:
                    logger.dot()

        read, write = os.pipe()
        dots_thread = threading.Thread(target=print_dots, args=(read, ))
        dots_thread.start()

        try:
            status = output_on_fail(process, outputs)
        finally:
            os.write(write, "done")
            dots_thread.join()
            os.close(read)
            os.close(write)

        return status

    return strategy


def running_output(process, outputs):
    """Show output of process as it runs."""
    logger = IndentedLogger()

    def output_printer(file_handle):
        """Thread that prints the output of this process."""
        read_first_byte = False

        while True:
            data = file_handle.read(1)
            if data:
                if not read_first_byte:
                    if data != "\n":
                        logger.message("\n")

                    read_first_byte = True

                logger.message(data)
            else:
                return

    stdout = threading.Thread(target=output_printer, args=(outputs[0], ))
    stderr = threading.Thread(target=output_printer, args=(outputs[1], ))

    stdout.start()
    stderr.start()

    try:
        status = process.wait()
    finally:
        stdout.join()
        stderr.join()

    return status


@contextmanager
def close_file_pair(pair):
    """Close the pair of files on exit."""
    try:
        yield pair
    finally:
        pair[0].close()
        pair[1].close()


@contextmanager
def in_dir(path):
    """Execute statements in this context in path."""
    cwd = os.getcwd()
    os.chdir(path)

    try:
        yield
    finally:
        os.chdir(cwd)


def execute(container, output_strategy, *args, **kwargs):
    """A thin wrapper around subprocess.Popen.

    This class encapsulates a single command. The first argument to the
    constructor specifies how this command's output should be handled
    (either suppressed, or forwarded to stderr). Remaining arguments
    will be passed to Popen.
    """
    env = os.environ.copy()

    if kwargs.get("env"):
        env.update(kwargs["env"])

    try:
        process = subprocess.Popen(args,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   env=env)
    except OSError, e:
        raise Exception("Failed to execute {0} - {1}".format(" ".join(args),
                                                             str(e)))

    with close_file_pair((process.stdout, process.stderr)) as outputs:
        status = output_strategy(process, outputs)

        instant_fail = kwargs.get("instant_fail") or False

        if status != 0:
            cmd = " ".join(args)
            logger = IndentedLogger()
            logger.message("!!! Process {0} failed with {1}".format(cmd,
                                                                    status))
            container.note_failure(instant_fail)

        return status


def which(executable):
    """Full path to executable."""
    def is_executable(file):
        """True if file exists and is executable."""
        return (os.path.exists(file) and
                not os.path.isdir(file) and
                os.access(file, os.F_OK | os.X_OK))

    def normalize(path):
        """Return canonical case-normalized path."""
        return os.path.normcase(os.path.realpath(path))

    def path_list():
        """Get executable path list."""
        return (os.environ.get("PATH") or os.defpath).split(os.pathsep)

    seen = set()

    for path in [normalize(p) for p in path_list()]:
        if path not in seen:
            full_path = os.path.join(path, executable)
            if is_executable(full_path):
                return full_path
            else:
                seen.add(path)

    return None


def where_unavailable(executable, function, *args, **kwargs):
    """Call function if executable is not available in PATH."""
    if which(executable) is None:
        return function(*args, **kwargs)

    return None


def url_opener():
    """Return a function that opens urls as files."""
    try:
        from urllib.request import urlopen
    except ImportError:
        from urllib2 import urlopen

    return urlopen


def url_error():
    """Return class representing a failed urlopen."""
    try:
        from urllib.error import URLError
    except ImportError:
        from urllib2 import URLError

    return URLError


def get_system_identifier(container):
    """Return an identifier which contains information about the ABI."""
    system_identifier_cache_dir = container.named_cache_dir("system-id")
    system_identifier_config_guess = os.path.join(system_identifier_cache_dir,
                                                  "config.guess")

    if not os.path.exists(system_identifier_config_guess):
        domain = "http://public-travis-autoconf-scripts.polysquare.org"
        config_project = "{0}/cgit/config.git/plain".format(domain)
        with open(system_identifier_config_guess, "w") as config_guess:
            remote = url_opener()(config_project + "/config.guess")
            config_guess.write(remote.read())

            os.chmod(system_identifier_config_guess,
                     os.stat(system_identifier_config_guess).st_mode |
                     stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return subprocess.check_output([system_identifier_config_guess]).strip()