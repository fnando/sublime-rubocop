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
from .utils import settings, SafeLoaderIgnoreUnknown, debug, run_rubocop, is_sublime_3


def find_root_dir_for_file(folders, file_name):
    if len(folders) == 0:
        return os.path.dirname(file_name)

    for folder in folders:
        if folder + "/" in file_name:
            return folder


class RubocopCompletionListener(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        window = view.window()
        folders = window.folders()
        file_name = view.file_name()
        prefix = prefix.lower()
        root_dir = find_root_dir_for_file(folders, file_name)

        debug("prefix:", prefix)
        debug("file name:", file_name)
        debug("folders:", folders)
        debug("root dir:", root_dir)
        debug("Python version:", platform.python_version())
        debug("debug?", settings("debug"))
        debug("rubocop command:", settings("rubocop_command"))
        debug("bundler command:", settings("bundler_command"))

        sel = view.sel()[0]
        line = view.substr(view.full_line(sel))
        cursor = sel.begin()
        (row_number, col_number) = view.rowcol(cursor)

        cache = self.get_cache(root_dir)

        cops = cache["cops"]

        completions = []
        completions += self.completions_for_ruby(cops, view, locations,
                                                 folders, root_dir, row_number,
                                                 col_number, line)
        completions += self.completions_for_yaml(cops, view, locations,
                                                 folders, root_dir, row_number,
                                                 col_number, line)

        if is_sublime_3():
            completions = sorted(completions, key=lambda item: item[0])

            return (completions, sublime.INHIBIT_WORD_COMPLETIONS
                    | sublime.INHIBIT_EXPLICIT_COMPLETIONS)
        else:
            completions = sorted(completions, key=lambda item: item.trigger)

            return sublime.CompletionList(
                completions, sublime.INHIBIT_WORD_COMPLETIONS
                | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    def get_cache(self, root_dir):
        cache_dir = os.path.join(sublime.packages_path(), "User", "RuboCop",
                                 "Cache")
        cache_dir_path = Path(cache_dir)
        schema_version = 2
        cache_name = self.compute_cache_name(schema_version, root_dir)
        cache_file = os.path.join(cache_dir, "%s.json" % cache_name)
        cache_file_path = Path(cache_file)

        debug("cache dir:", cache_dir)
        debug("cache file:", cache_file_path)
        debug("cache file exists:", cache_file_path.is_file())

        if cache_file_path.is_file():
            debug("returning existing cache")

            with open(cache_file) as file:
                return json.load(file)

        debug("running commmand to fetch cops")
        (success, stdout) = run_rubocop(["--show-cops"], folder=root_dir)

        if not success:
            debug("failed to fetch cops")
            return {"cops": []}

        cops = yaml.load(stdout, Loader=SafeLoaderIgnoreUnknown)
        cache = {"version": schema_version, "cops": cops}

        if not cache_dir_path.is_dir():
            os.makedirs(cache_dir, exist_ok=True)

        with open(cache_file, "w") as file:
            json.dump(cache, file, indent=2)

        return cache

    def compute_cache_name(self, schema_version, root_dir):
        components = [str(schema_version)]

        rubocop_config_path = Path(os.path.join(root_dir, ".rubocop.yml"))
        bundler_config_path = Path(os.path.join(root_dir, "Gemfile.lock"))

        if rubocop_config_path.is_file():
            with open(str(rubocop_config_path), "r") as file:
                components.append(
                    hashlib.sha1(file.read().encode("utf-8")).hexdigest())

        if bundler_config_path.is_file():
            with open(str(bundler_config_path), "r") as file:
                components.append(
                    hashlib.sha1(file.read().encode("utf-8")).hexdigest())

        return hashlib.sha1("".join(components).encode("utf-8")).hexdigest()

    def find_previous_line_matching_regex(self, view, current_row_number,
                                          pattern):
        while current_row_number > 0:
            current_row_number -= 1
            line = view.substr(
                view.full_line(
                    view.line(
                        sublime.Region(view.text_point(current_row_number,
                                                       0)))))
            matches = re.match(pattern, line)

            if matches:
                return matches

        return

    def completions_for_yaml(self, cops, view, locations, folders, root_dir,
                             row_number, col_number, line):
        completions = []
        line = line.replace('\n', '')

        # Make sure we're in YAML context.
        if not view.match_selector(locations[0], "source.yaml"):
            debug("not a yaml file, skipping...")
            return []

        debug("getting completions for yaml file")
        debug("column number:", col_number)
        debug("line number:", row_number)
        debug("line has two spaces?", line == "  ")
        debug("line: ->%s<-" % (line))

        use_cop_completion = col_number == 0
        use_attribute_completion = col_number == 2 and line == "  "
        use_value_completion = re.match(r"  (.*?):\s*", line)

        debug("use cop completion?", use_cop_completion)
        debug("use attribute completion?", use_attribute_completion)
        debug("use value completion?", use_value_completion != None)

        # Make sure we're at the right position.
        if use_cop_completion:
            for name in cops:
                cop = cops[name]

                completions.append(
                    self.build_cop_completion_st3(cop, name) if is_sublime_3(
                    ) else self.build_cop_completion(cop, name))

        if use_value_completion is not None:
            attr = use_value_completion.group(1)

            if attr != "EnforcedStyle":
                debug(attr, "doesn't support completion")
                return completions

            matches = self.find_previous_line_matching_regex(
                view, row_number, r"""^([a-zA-Z0-9/]+):$""")

            if not matches:
                return completions

            cop_name = matches.group(1)
            cop = cops.get(cop_name)
            debug("cop name:", cop_name)
            debug("attribute:", attr)

            if cop is None:
                return completions

            values = cop.get("SupportedStyles")

            if values is None:
                return completions

            debug("values:", values)

            for value in values:
                snippet_str = str(value)

                if is_sublime_3():
                    completion = self.build_value_completion_st3(value)
                else:
                    completion = self.build_value_completion(value)

                completions.append(completion)

        if use_attribute_completion:
            matches = self.find_previous_line_matching_regex(
                view, row_number, r"""^([a-zA-Z0-9/]+):$""")

            if not matches:
                return completions

            cop_name = matches.group(1)

            cop = cops.get(cop_name)
            debug("try completion for", cop_name, "properties. Found?",
                  cop != None)

            if cop is None:
                return completions

            debug("cop is", cop)

            for attr in cop.keys():
                if "EnforcedStyle" in cop:
                    value = cop["EnforcedStyle"]
                else:
                    value = cop[attr]

                snippet_str = str(value)
                value_str = str(cop[attr])

                if is_sublime_3():
                    completion = self.build_attribute_completion_st3(
                        cop_name, attr, value_str, snippet_str)
                else:
                    completion = self.build_attribute_completion(
                        cop_name, attr, value_str, snippet_str)

                completions.append(completion)

        return completions

    def build_cop_completion(self, cop, cop_name):
        return sublime.CompletionItem(
            cop_name,
            completion="%s:\n  " % cop_name,
            details="%s%s" % (cop["Description"], self.docs_link(cop_name)),
            annotation="Cop",
            kind=sublime.KIND_KEYWORD)

    def build_cop_completion_st3(self, cop, cop_name):
        return ["%s" % cop_name]

    def build_attribute_completion_st3(self, cop_name, attr, value, snippet):
        return ["%s" % attr, "%s: ${1:%s}" % (attr, snippet)]

    def build_attribute_completion(self, cop_name, attr, value, snippet):
        return sublime.CompletionItem.snippet_completion(
            attr,
            snippet="%s: ${1:%s}" % (attr, snippet),
            annotation="Property",
            kind=sublime.KIND_VARIABLE,
            details="Default: %s%s" % (value, self.docs_link(cop_name)))

    def build_value_completion(self, value):
        return sublime.CompletionItem(value,
                                      completion=value,
                                      annotation="Value",
                                      kind=sublime.KIND_KEYWORD)

    def completions_for_ruby(self, cops, view, locations, folders, root_dir,
                             row_number, col_number, line):
        # Make sure we're in Ruby context.
        if not view.match_selector(locations[0], "source.ruby"):
            debug("not a ruby file, skipping...")
            return []

        # Also, let's ensure we're in pound-comment section.
        if not view.match_selector(locations[0], "comment.line.number-sign"):
            debug("not a pound-comment section, skipping...")
            return []

        debug("getting completions for ruby file")

        annotation = "rubocop:disable"
        annotation_index = line.rfind(annotation)
        annotation_position = annotation_index + len(annotation) + 1
        debug("cursor:", col_number, "annotation position:",
              annotation_position)

        # Check if there's a `rubocop:disable` annotation
        if annotation_index == -1 or col_number < annotation_position:
            spaces = None

            if line[col_number - 1] == "#":
                spaces = " "
            elif line[col_number - 2] == "#":
                spaces = ""

            if spaces is not None:
                return [
                    sublime.CompletionItem(
                        "rubocop:disable",
                        completion=" rubocop:disable ",
                        details="Disable one or more RuboCop rules",
                        kind=sublime.KIND_MARKUP)
                ]

            debug("cursor is not in right place, skipping...")
            return []

        completions = []

        for name in cops:
            cop = cops[name]
            description = cop["Description"].replace("<", "&lt;").replace(
                ">", "&gt;").replace("&", "&amp;")

            completions.append(
                sublime.CompletionItem(name,
                                       completion=name,
                                       details="%s%s" %
                                       (description, self.docs_link(name)),
                                       annotation="Cop",
                                       kind=sublime.KIND_KEYWORD))

        return completions

    def docs_link(self, name):
        department = name.split("/")[0].lower()
        fragment = name.lower().replace("/", "")

        if department == "rails":
            url = "https://docs.rubocop.org/rubocop-rails/cops_%s.html#%s"
        elif department == "performance":
            url = "https://docs.rubocop.org/rubocop-performance/cops_%s.html#%s"
        else:
            url = "https://docs.rubocop.org/rubocop/cops_%s.html#%s"

        url = url % (department, fragment)

        return " <a href='%s'>More</a>" % url
