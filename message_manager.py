from __future__ import print_function
# import os
from operator import itemgetter
from collections import OrderedDict
from operator import attrgetter

import sublime
import sublime_plugin

from . import multiconf


def plugin_loaded():
    global message_manager, _tmp_sources
    # resurrect previously loaded sources on plugin reload
    try:
        for src, priority in _tmp_sources:
            message_manager.add_source(src, priority)
        del _tmp_sources
    except NameError:
        pass

def plugin_unloaded():
    global message_manager, _tmp_sources
    # save the sources to be resurrected later
    _tmp_sources = message_manager.sources
    del message_manager


class FileInfoDict(dict):
    """ keys of this dict should be integer line numbers """
    root_view = None  # View or None
    saved_regions = None  # dict of regions or None

    def __init__(self, *args, **kwargs):
        super(FileInfoDict, self).__init__(*args, **kwargs)


class ErrorInfo(object):
    """ contains meta data about an error """
    orig_line = None  # int, line when build was run, region may have moved
    severity = None  # str in markers.keys()
    message = None  # str
    order = None
    extra = None
    errid = None
    symbol = None
    # region = None  # None, or a sublime text region for marking a line

    def __init__(self, src, line, severity, message, extra=False, errid=None,
                 symbol=None):
        # if severity is not recognized, choose the lowest one
        keys = list(src.markers.keys())
        try:
            self.order = keys.index(severity)
        except ValueError:
            severity = keys[0]
            self.order = 0
        self.orig_line = line
        self.severity = severity
        self.message = message
        self.extra = extra
        self.errid = errid
        self.symbol = symbol
        self.order = src.sev_lookup[severity]


class LineMessageManager(object):
    """ Manages a bunch of LineMessageSources, the source take care of getting
    called and populating its own list of errors / messages, and the manager
    takes care of updating the regions and toolbar message, and most
    importantly, keeping the regions on the right lines when changes are made
    to the file.
    """

    sources = None

    def __init__(self):
        self.sources = []

    def add_source(self, src, priority=0):
        """ add a source, then resort the sources by priority, in the event
        of a duplicate, clobber the old one, this is so we don't have
        tons of sources when reloading source plugins """
        for i in range(len(self.sources)):
            # make sure we're not duplicating source types, typical of
            # plugin reload
            # can't use isinstance since the reloaded class is not the same
            if str(src.__class__) == str(self.sources[i][0].__class__):
                print("MessageManager:", str(src.__class__),
                      "already exists... removing the old one")
                self.sources.pop(i)
                break
        self.sources.append([src, priority])
        self.sources.sort(key=itemgetter(1))

    def del_source(self, src):
        for i in range(len(self.sources)):
            if src is self.sources[i][0]:
                self.sources.pop(i)
                break

    def change_src_priority(self, src, priority):
        for i in range(len(self.sources)):
            if src is self.sources[i][0]:
                self.sources[i][1] = priority
        self.sources.sort(key=itemgetter(1))

    def clear_view(self, view):
        for src, priority in self.sources:
            src.clear_view(view)

    def clear_window(self, window):
        for src, priority in self.sources:
            src.clear_window(window)

    def mark_errors(self, window, view):
        for src, priority in self.sources:
            src.mark_errors(window, view)

    def change_status_message(self, window, view, point):
        """ if we want to update the status message for cursor changes, etc.
        then check all sources to see if this view has messages, and if so,
        check all messages to change the status line """
        try:
            w_id = window.id()
            fname = view.file_name()
        except AttributeError:
            return None

        # print(point)
        for src, priority in self.sources:
            # print(src)
            if w_id in src.messages and fname in src.messages[w_id]:
                err_reg = None
                for severity in src.markers.keys():
                    regions = view.get_regions(src.marker_key + severity)
                    for reg in regions:
                        if reg.contains(point):
                            err_reg = reg
                            break
                    if err_reg is not None:
                        break

                msg = None
                if err_reg is not None:
                    msg = ""
                    for info in src.messages[w_id][fname][int(err_reg.xpos)]:
                        if info.message is not None:
                            if msg != "":
                                msg += " "
                            msg += info.message

                if msg is None:
                    view.erase_status(src.status_key)
                else:
                    view.set_status(src.status_key, msg)

    def get_err_list(self, view):
        """ return a list of ErrorInfo objects for all sources sorted by
        line, then by severity """
        window = view.window()
        # view_id = self.view.id()
        fname = view.file_name()
        w_id = window.id()

        errlst = []

        for src, _ in self.sources:
            if w_id in src.messages and fname in src.messages[w_id]:
                l = []
                for li in src.messages[w_id][fname].values():
                    l += li
                errlst += l
        errlst.sort(key=attrgetter("orig_line"))
        return errlst

    def change_root_view(self, view):
        window = sublime.active_window()
        w_id = window.id()
        fname = view.file_name()
        for src, _ in self.sources:
            if w_id in src.messages and fname in src.messages[w_id]:
                f_info = src.messages[w_id][fname]
                # if this was the root view, look for another to take
                # ownership of the file info object
                if f_info.root_view == view:
                    f_info.root_view = None
                    for other in window.views():
                        if other.file_name() == fname and other is not view:
                            f_info.root_view = other
                            break

class LineMessageSource(object):
    """ This class does the interfacing with whatever layer wants to have line
    messages, whether it's a build system, or a linter, etc.
    """

    _settings = None
    messages = None

    # these can be set when you override the class
    prefix = None  # for internal tags
    pretty_prefix = None # for status message, filled by init of not overridden
    # order indicates severity / preference of icon when > 1 err on a line
    # the value is a tuple of (marker type or icon path, scope name)
    markers = OrderedDict([("info", ("dot", "SublimeMessages.info")),
                           ("warning", ("circle", "SublimeMessages.warning")),
                           ("error", ("bookmark", "SublimeMessages.error"))])
    sev_lookup = None

    # these get initialized by __init__ from self.prefix
    marker_key = None
    status_key = None

    def __init__(self):
        if self.pretty_prefix is None:
            self.pretty_prefix = self.prefix

        if self.marker_key is None:
            self.marker_key = self.prefix + "_mark."
        if self.status_key is None:
            self.status_key = self.prefix + "_stat"

        self.sev_lookup = {s: i for i, s in enumerate(self.markers)}

        self.messages = {}
        self._load_settings()

    @property
    def priority(self):
        return multiconf.get(self.settings, "priority", 0)

    @property
    def enabled(self):
        return multiconf.get(self.settings, "enabled", 0)

    @property
    def settings(self):
        if self._settings is None:
            self._load_settings()
        return self._settings

    def _load_settings(self):
        prefix = self.prefix
        settings_fname = "Messages" + prefix + ".sublime-settings"
        self._settings = sublime.load_settings(settings_fname)

        key = prefix + "MessageSource"
        self._settings.clear_on_change(key)  # is this necessary?
        self._settings.add_on_change(key, self.settings_callback)

    def settings_callback(self):
        message_manager.change_src_priority(self, self.priority)

    def clear_view(self, view):
        for sev in self.markers.keys():
            view.erase_regions(self.marker_key + sev)
        view.erase_status(self.status_key)

    def clear_window(self, window):
        for view in window.views():
            self.clear_view(view)

        # remove all info about the error list
        try:
            del self.messages[window.id()]
        except KeyError:
            pass

    def run(self, view):
        """ run should be automatically called by the manager when it wants.
        Not all message sources will need a run, like the sublemake build """
        raise NotImplementedError()

    def mark_errors(self, window, view):
        """ This creates regions with icons in the gutter, and should be
        called on all views when the messages dict gets filled, or on a
        view when it is created """
        w_id = window.id()
        fname = view.file_name()
        self.clear_view(view)
        if w_id not in self.messages or fname not in self.messages[w_id]:
            window.run_command("mark_errors_update_status")
            return None

        f_info = self.messages[w_id][fname]
        regions = dict((key, []) for key in self.markers.keys())

        # this is for a cloned view i think
        if f_info.root_view is not None:
            root_view = f_info.root_view
            for severity in self.markers.keys():
                regions[severity] = root_view.get_regions(self.marker_key + \
                                                          severity)
        # this exists when a view is saved so it can be re-opened properly?
        elif f_info.saved_regions is not None:
            regions = f_info.saved_regions
            f_info.root_view = view
        # normal operation, parse the err info into regions
        else:
            for errinfo_lst in f_info.values():
                # the first one will be the most severe on the line, so that's
                # the icon that should appear, then there's no real reason for
                # the others as far as regions go
                errinfo = errinfo_lst[0]
                line_reg = view.line(view.text_point(errinfo.orig_line - 1, 0))
                line_reg.xpos = errinfo.orig_line
                # if errinfo.severity in self.markers:
                sev = errinfo.severity
                regions[sev].append(line_reg)
            f_info.root_view = view

        for severity, region_lst in regions.items():
            key = self.marker_key + severity
            icon = self.markers[severity][0]
            scope = self.markers[severity][1]
            # if icon == "dot":
            #     icon = "Packages/sublemake/icons/dot.png"
            view.add_regions(key, region_lst, scope,
                             icon, sublime.HIDDEN)

        # change_status_message(window, view, view.sel()[0].end())
        window.run_command("mark_errors_update_status")
        return None


# these need to be cleaned up for scope of which errors to remove
class ClearAllLineMessagesCommand(sublime_plugin.WindowCommand):
    def run(self):
        message_manager.clear_window(self.window)


class ClearViewLineMessagesCommand(sublime_plugin.WindowCommand):
    def run(self):
        message_manager.clear_view(self.window.active_view())


class MarkErrorsUpdateStatus(sublime_plugin.WindowCommand):
    def run(self):
        window = self.window
        view = window.active_view()
        point = view.sel()[0].end()
        message_manager.change_status_message(window, view, point)


class MarkErrorsListCommand(sublime_plugin.TextCommand):
    last_selected = 0

    def run(self, edit, **kwargs):
        view = self.view
        window = view.window()
        err_lst = message_manager.get_err_list(view)

        msgs = [li.message for li in err_lst]
        line_nums = [li.orig_line for li in err_lst]

        pre_position = view.viewport_position()
        if self.last_selected >= len(msgs):
            self.last_selected = 0

        def on_done(selected_item):
            if selected_item == -1:
                self.view.set_viewport_position(pre_position)
                return
            self.last_selected = selected_item
            self.view.run_command("goto_line",
                                  {"line": line_nums[selected_item]})
        def on_highlight(selected_item):
            if selected_item == -1:
                return
            view = self.view
            view.show_at_center(view.text_point(line_nums[selected_item], 0))

        window.show_quick_panel(msgs, on_done, 0, self.last_selected,
                                on_highlight)

class LineMessageListener(sublime_plugin.EventListener):
    prev_line = None  # int

    def __init__(self):
        super(LineMessageListener, self).__init__()

    # @staticmethod
    # def on_pre_save(view):
    #     w_id = view.window().id()
    #     fname = view.file_name()
    #     if w_id in _errors and fname in _errors[w_id]:
    #         regions = {}
    #         for severity in self.markers.keys():
    #             regions[severity] = view.get_regions(__marker_key__ + severity)
    #         _errors[w_id][fname].saved_regions = regions

    @staticmethod
    def on_close(view):
        # print("close", view.file_name())
        message_manager.change_root_view(view)

    @staticmethod
    def on_clone(view):
        # print("clone", view.file_name())
        message_manager.mark_errors(sublime.active_window(), view)

    @staticmethod
    def on_load(view):
        # print("load", view.file_name())
        message_manager.mark_errors(sublime.active_window(), view)

    # @staticmethod
    # def on_text_command(view, command_name, args):
    #     if command_name == "Revert":
    #         mark_errors(sublime.active_window(), view)

    def on_activated(self, view):
        view.window().run_command("mark_errors_update_status")

    def on_selection_modified(self, view):
        point = view.sel()[0].end()
        line = view.rowcol(point)[0]
        # print("id: ", view.id(), "lines:", self.prev_line, line)

        # TODO, what if we switch views, but the line number is the same?
        if self.prev_line != line:
            message_manager.change_status_message(view.window(), view, point)
            self.prev_line = line


# declare the global message_manager, doing this at plugin_loaded is too late
# for plugins that are loaded before this one
message_manager = LineMessageManager()

##
## EOF
##
