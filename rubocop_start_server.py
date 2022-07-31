import sublime_plugin
from .utils import start_rubocop


class RubocopStartServer(sublime_plugin.WindowCommand):
    def run(self, restart=False):
        print(start_rubocop(self.window.folders(), restart=restart))
