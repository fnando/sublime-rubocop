import sublime
import sublime_plugin
import os
import hashlib
import re
from subprocess import Popen, PIPE
import platform
import yaml
import json
from pathlib import Path
from .utils import settings, SafeLoaderIgnoreUnknown, debug, start_rubocop, stop_rubocop, run_rubocop, is_sublime_3, clear_cache


def plugin_loaded():
    clear_cache()


class RubocopListener(sublime_plugin.EventListener):
    def on_post_save_async(self, view):
        file_path = Path(view.file_name())
        folders = view.window().folders()
        basename = os.path.basename(view.file_name())

        if basename != ".rubocop.yml":
            return

        start_rubocop(folders)

    def on_new_window_async(self, window):
        start_rubocop(window.folders())

    def on_window_command(self, window, cmd, args):
        if cmd == "close_window":
            stop_rubocop(window.folders())

    def on_pre_close_window(self, window):
        stop_rubocop(window.folders())
