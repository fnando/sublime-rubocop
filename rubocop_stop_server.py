import sublime_plugin
from .utils import stop_rubocop


class RubocopStopServer(sublime_plugin.WindowCommand):
    def run(self):
        stop_rubocop(self.window.folders())
