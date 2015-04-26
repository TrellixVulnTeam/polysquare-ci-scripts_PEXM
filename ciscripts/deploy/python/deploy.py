# /ciscripts/deploy/python/deploy.py
#
# Activate haskell container in preparation for deployment. This is required
# because we need to have pandoc available in our PATH.
#
# See /LICENCE.md for Copyright information
"""Place a symbolic link of pandoc in a writable directory in PATH."""

import os


def run(cont, util, shell, argv=None):
    """Place a symbolic link of pandoc in a writable directory in PATH."""
    del argv

    with util.Task("""Preparing for deployment to PyPI"""):
        hs_ver = "7.8.4"
        hs_script = "setup/project/configure_haskell.py"
        hs_cont = cont.fetch_and_import(hs_script).get(cont,
                                                       util,
                                                       shell,
                                                       hs_ver)

        with hs_cont.activated(util):
            pandoc_binary = os.path.realpath(util.which("pandoc"))

        if os.environ.get("CI", None):
            # Find the first directory in PATH that is in /home, eg
            # writable by the current user and make a symbolic link
            # from the pandoc binary to.
            if not util.which("pandoc"):
                home_dir = os.path.expanduser("~")
                languages = cont.language_dir("")
                # Filter out paths in the container as they won't
                # be available during the deploy step.
                for path in os.environ.get("PATH", "").split(":"):
                    in_home = (os.path.commonprefix([home_dir,
                                                     path]) == home_dir)
                    in_container = (os.path.commonprefix([languages,
                                                          path]) == languages)

                    if in_home and not in_container:
                        destination = os.path.join(path, "pandoc")
                        with util.Task("""Creating a symbolic link from """
                                       """{0} to {1}.""".format(pandoc_binary,
                                                                destination)):
                            os.symlink(pandoc_binary, destination)
                            break
