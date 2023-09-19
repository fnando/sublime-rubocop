import sublime
import yaml
from pathlib import Path
import os
from subprocess import Popen, PIPE
import shutil


def is_sublime_3():
    return sublime.version()[0] == "3"


def settings(key):
    return sublime.load_settings("RuboCop.sublime-settings").get(key)


def debug(*args):
    if settings("debug"):
        print("[RuboCop]", *args)


class SafeLoaderIgnoreUnknown(yaml.SafeLoader):
    def ignore_unknown(self, node):
        return None


SafeLoaderIgnoreUnknown.add_constructor(None,
                                        SafeLoaderIgnoreUnknown.ignore_unknown)


def start_rubocop(folders, restart=False):
    for folder in folders:
        run_rubocop(["--restart-server"], folder=folder)


def stop_rubocop(folders):
    for folder in folders:
        run_rubocop(["--stop-server"], folder=folder)


def run_rubocop(args, folder=None):
    rubocop_config_file = Path(os.path.join(folder, ".rubocop.yml"))
    bundler_config_file = Path(os.path.join(folder, "Gemfile"))

    if folder is None:
        debug("no folder provided, so skipping")
        return (False, "")

    if not rubocop_config_file.is_file():
        debug("no rubocop config file found, so no need to stop server")
        return (False, "")

    cmd = []

    if settings("bundler") and bundler_config_file.is_file():
        cmd += [settings("bundler_command"), "exec", "rubocop"]
    else:
        cmd += [settings("rubocop_command")]

    cmd += args

    if settings("server") and ("--stop-server"
                               not in cmd) and ("--restart-server" not in cmd):
        cmd += ["--server"]

    debug("running command", cmd, "for", folder)
    os.chdir(folder)

    result = Popen(
        cmd,
        stdout=PIPE,
        stderr=PIPE,
        cwd=folder,
        close_fds=True,
    )

    stdout = result.stdout.read()
    stderr = result.stderr.read()
    success = len(stderr) == 0

    debug("stderr:")
    debug(stderr)

    return success, stdout


def clear_cache():
    debug("clearing cache")

    cache_dir = Path(
        os.path.join(sublime.packages_path(), "User", "RuboCop", "Cache"))

    if cache_dir.is_dir():
        shutil.rmtree(str(cache_dir))
