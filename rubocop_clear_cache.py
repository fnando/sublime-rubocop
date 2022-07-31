import sublime
import sublime_plugin
from .utils import clear_cache


class RubocopClearCache(sublime_plugin.WindowCommand):
    def run(self):
        clear_cache()
