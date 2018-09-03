# -*- coding: utf-8 -*-
import os
import sys
import re
import logging
import getpass
from argparse import ArgumentParser

os.environ['QT_API'] = 'pyside2'

from qtpy import QtWidgets, QtGui, QtCore, QtNetwork

import bd.config.loader
from bd.exceptions import *

LOGGER = logging.getLogger("bd.desktop")


BD_DEVEL = "BD_DEVEL" in os.environ

BD_PIPELINE_DIR = os.getenv("BD_PIPELINE_DIR", "/Volumes/asset/pipeline")

BD_RESOURCES_DIR = os.path.join(BD_PIPELINE_DIR, "resources")

APP_ICON = os.path.join(BD_RESOURCES_DIR, "icons", "logo_bd.ico")
PRESET_ICON = os.path.join(BD_RESOURCES_DIR, "icons", "preset.png")
PROJECT_ICON = os.path.join(BD_RESOURCES_DIR, "icons", "project.png")
LAUNCHER_ICON = os.path.join(BD_RESOURCES_DIR, "icons", "launcher.png")


def px(value):
    return QtGui.QFontMetrics(app.font()).width("o") / 5.0 * value


class Messenger(QtCore.QObject):
    """Qt implementation of the 'observer' pattern.

    Objects connect to each other through the instance of
    this class, thus decoupling the whole system.

    """

    project_infos_ready = QtCore.Signal(list)
    preset_infos_ready = QtCore.Signal(list)
    launcher_infos_ready = QtCore.Signal(list)

    project_selected = QtCore.Signal(dict)
    preset_selected = QtCore.Signal(dict)
    launcher_selected = QtCore.Signal(dict)

    settings_menu_activated = QtCore.Signal()

    def __init__(self):
        super(Messenger, self).__init__()

        self._project = None
        self._preset = None

        self.project_selected.connect(self._on_project_selected)
        self.preset_selected.connect(self._on_preset_selected)

    def _on_project_selected(self, project_info):
        self._project = project_info["name"]

    def _on_preset_selected(self, preset_info):
        self._preset = preset_info["name"]

    def get_project(self):
        return self._project

    def get_preset(self):
        return self._preset


messenger = Messenger()


class LauncherItemDelegate(QtWidgets.QStyledItemDelegate):
    """Styled item delegate to draw the last"""
    def __init__(self, parent=None):
        super(LauncherItemDelegate, self).__init__(parent)
        self._hover_row = None
        self._margin = px(4)

    def paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        painter.save()

        row = index.row()
        col = index.column()

        # check whether the current index is on the selected row
        is_selected = self.parent().selectionModel().isRowSelected(row, index.parent())

        # rectangle for the current row
        #
        rect = QtCore.QRect(option.rect)

        # make margins to simlessly transition from left to right cells
        #
        rect.adjust(self._margin if col == 0 else 0,
                    self._margin,
                    -self._margin if col != 0 else 0,
                    -self._margin)

        if row == self._hover_row or is_selected:

            # fill a whole background including margins
            #
            painter.fillRect(option.rect, QtGui.QColor("#232629"))

            # which color value to choose for the rectangle
            # it should be dimmer on mouse over
            #
            color_value = 80 if is_selected else 50

            # paint selection rectangle
            #
            painter.fillRect(rect, QtGui.QColor(color_value, color_value, color_value))

            # paint the small blue rectangle on the right side
            #
            if col != 0:
                painter.fillRect(
                    rect.adjusted(rect.width() - px(2), 0, 0, 0),
                    option.palette.highlight()
                )

        if col == 0:
            # draw all the default components
            #
            ApplicationSingleton.instance().style().drawControl(
                QtWidgets.QStyle.CE_ItemViewItem,
                opt,
                painter,
                self.parent()
            )
        else:
            has_multi_versions = len(index.data(QtCore.Qt.UserRole)["versions"]) > 1

            # make the text brighter on mouse over
            if has_multi_versions and option.state & QtWidgets.QStyle.State_MouseOver:
                painter.setPen(QtCore.Qt.white)
            else:
                painter.setPen(QtCore.Qt.gray)

            font = painter.font()
            font.setPixelSize(px(8))
            painter.setFont(font)

            rect.setRight(rect.right() - px(2))

            text = index.data(QtCore.Qt.DisplayRole)
            painter.drawText(rect.adjusted(0, 0, -px(15), 0),
                             QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight,
                             text)

            if has_multi_versions:

                font = painter.font()
                font.setPixelSize(px(6))
                painter.setFont(font)

                painter.drawText(rect.adjusted(rect.width() - px(15), 0, 0, 0),
                                 QtCore.Qt.AlignCenter,
                                 u"▼")
        painter.restore()

    def on_hover_index_changed(self, index):
        self._hover_row = index.row()

    def createEditor(self, parent, option, index):
        if index.column() == 1:

            has_multi_versions = len(index.data(QtCore.Qt.UserRole)["versions"]) > 1
            if not has_multi_versions:
                return

            editor = QtWidgets.QMenu(self.parent())
            editor.setAutoFillBackground(True)
            editor.aboutToHide.connect(self._commit_and_close)

            font = QtWidgets.qApp.font()
            font.setPixelSize(px(8))
            editor.setFont(font)

            return editor

    def setEditorData(self, editor, index):
        editor.setStyleSheet("border-top: none")

        data = index.data(QtCore.Qt.UserRole)
        for version in data["versions"]:
            editor.addAction(version)

        sibling_index = index.sibling(index.row(), 1 - index.column())
        current_rect = self.parent().visualRect(index)
        sibling_rect = self.parent().visualRect(sibling_index)

        rect = current_rect.united(sibling_rect)
        rect.adjust(self._margin, self._margin, -self._margin, -self._margin)

        editor.setFixedWidth(rect.width())

        pos = self.parent().mapToGlobal(rect.bottomLeft())

        editor.popup(pos)

    def setModelData(self, editor, model, index):
        action = editor.activeAction()
        if not action:
            return

        data = index.data(QtCore.Qt.UserRole)
        data["active_version"] = str(action.text())
        index.model().setData(index, data)

    def _commit_and_close(self):
        editor = self.sender()
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, self.NoHint)


class ItemModel(QtCore.QAbstractTableModel):

    def __init__(self, protocol, column_count=1, editable_column=None):
        super(ItemModel, self).__init__()
        self._data = None

        self._rows = 0
        self._cols = column_count

        self._editable_column = editable_column

        self._protocol = protocol

    def update(self, data):
        self.layoutAboutToBeChanged.emit()

        self._data = data

        self._rows = len(self._data)

        self.layoutChanged.emit()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return self._rows

    def columnCount(self, parent=QtCore.QModelIndex()):
        return self._cols

    def data(self, index, role):
        if not self._data:
            return

        if not index.isValid():
            return

        return self._protocol(role, index, self._data)

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if role == QtCore.Qt.EditRole:
            row = index.row()
            self._data[row] = value
            self.dataChanged.emit(index, index)
            return True

    def flags(self, index):
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        if index.isValid() and \
                self._editable_column is not None \
                        and index.column() == self._editable_column:
            flags |= QtCore.Qt.ItemIsEditable
        return flags


class ProjectsView(QtWidgets.QListView):

    def __init__(self, parent=None):
        super(ProjectsView, self).__init__(parent)
        self.setUniformItemSizes(True)
        self._init_ui()

    def _init_ui(self):
        self.setIconSize(QtCore.QSize(px(20), px(20)))
        self.setStyleSheet("""
QAbstractItemView::item {{
    height: {height}px;
    margin: {margin}px;
    padding: 0px;
    padding-left: {padding_left}px;
}}
QAbstractItemView::item:hover {{
    background: rgb(50, 50, 50);
    border-right: {border_width}px solid palette(highlight);
}}
QAbstractItemView::item:selected {{
    background: rgb(80, 80, 80);
    border-right: {border_width}px solid palette(highlight);
}}
""".format(height=px(28),
           margin=px(4),
           padding_left=px(3),
           border_width=px(2)))


class PresetsView(ProjectsView):

    def __init__(self, parent=None):
        super(PresetsView, self).__init__(parent)


class LaunchersView(QtWidgets.QTableView):

    hover_index_changed = QtCore.Signal(QtCore.QModelIndex)

    def __init__(self, parent=None):
        super(LaunchersView, self).__init__(parent)

        self._row_hovered = None

        self._editing_accepted = True
        self._was_editing = False

        self.setMouseTracking(True)
        self._last_mouse_release_time = QtCore.QTime.currentTime()

        self._init_ui()

    def _init_ui(self):
        self.verticalHeader().setDefaultSectionSize(px(36))
        self.verticalHeader().hide()
        self.horizontalHeader().hide()

        self.setShowGrid(False)

        self.setEditTriggers(self.NoEditTriggers)

        self.setIconSize(QtCore.QSize(px(20), px(20)))
        self.setSelectionMode(self.SingleSelection)
        self.setSelectionBehavior(self.SelectRows)

        delegate = LauncherItemDelegate(self)

        self.hover_index_changed.connect(delegate.on_hover_index_changed)
        self.setItemDelegate(delegate)

        self.setStyleSheet("""
QTableView::item {{
    margin: {margin}px;
    padding: 0px;
    padding-left: {padding_left}px;
    background: transparent;
}}
""".format(margin=px(4),
           padding_left=px(3)))

    def mouseMoveEvent(self, event):
        index = self.indexAt(event.pos())
        if index.isValid():
            row = index.row()
            if row != self._row_hovered:
                self.hover_index_changed.emit(index)

        return super(LaunchersView, self).mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:

            index = self.indexAt(event.pos())

            if index.isValid() and index.column() == 1:
                self._editing_accepted = True
                QtCore.QTimer.singleShot(300, lambda: self._on_timeout(index))

        return super(LaunchersView, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:

            index = self.indexAt(event.pos())

            if index.isValid() and index.column() == 1:

                current_time = QtCore.QTime.currentTime()

                if not self._was_editing and \
                        self._last_mouse_release_time.msecsTo(current_time) < 300:
                    self._editing_accepted = False

                self._was_editing = False
                self._last_mouse_release_time = current_time

        return super(LaunchersView, self).mouseReleaseEvent(event)

    def _on_timeout(self, index):
        if self._editing_accepted:
            self._was_editing = True
            self.edit(index)

    def resizeEvent(self, event):
        width = event.size().width()
        self.setColumnWidth(0, width * 0.5)
        self.setColumnWidth(1, width * 0.5)


class NavigationBar(QtWidgets.QWidget):

    back_button_clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super(NavigationBar, self).__init__(parent)
        self._init_ui()
        self._init_layout()
        self._init_signals()

    def _init_ui(self):
        self.setFixedHeight(px(25))
        self._back_button = QtWidgets.QToolButton(self)
        self._back_button.setIcon(
            QtGui.QIcon(os.path.join(BD_RESOURCES_DIR, "icons", "toolbutton_back.png"))
        )
        self._back_button.setIconSize(QtCore.QSize(px(5), px(5)))
        self._back_button.setFocusPolicy(QtCore.Qt.NoFocus)
        self._back_button.setFixedSize(px(20), px(20))
        self._back_button.setToolTip("Click to go back")

        self._back_button.setStyleSheet("border: none")
        self._back_button.hide()

        self._page_name_label = QtWidgets.QLabel("")
        self._page_name_label.setStyleSheet("color: rgb(180, 180, 180)")

        self._page_name_label.setFixedHeight(px(20))

        font = QtWidgets.qApp.font()
        font.setPixelSize(px(8))
        font.setBold(True)
        self._page_name_label.setFont(font)

        self._project_icon = QtWidgets.QLabel(self)

        img = QtGui.QImage(PROJECT_ICON)
        img = img.alphaChannel()

        color = QtGui.QColor(120, 120, 120)
        for i in range(img.colorCount()):
            color.setAlpha(QtGui.qGray(img.color(i)))
            img.setColor(i, color.rgba())

        pixmap = QtGui.QPixmap.fromImage(img)
        pixmap.setDevicePixelRatio(QtWidgets.qApp.devicePixelRatio())

        self._project_icon.setPixmap(
            pixmap.scaled(
                px(10),
                px(10),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
        )
        self._project_icon.hide()

        self._project_label = QtWidgets.QLabel(self)
        self._project_label.setToolTip("Currently active project")

        self._project_label.setFont(font)

        self._project_label.setStyleSheet("""color: rgb(120, 120, 120)""")
        self._project_label.hide()

    def _init_layout(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._back_button)
        layout.addWidget(self._page_name_label)

        layout.addStretch(1)

        layout.addWidget(self._project_icon)
        layout.addWidget(self._project_label)
        layout.addSpacing(px(12))

        layout.setAlignment(QtCore.Qt.AlignVCenter)

    def _init_signals(self):
        self._back_button.clicked.connect(self.back_button_clicked.emit)

    def update(self, page_name, page_index):
        if page_index == 0:
            self._back_button.hide()
            self._project_icon.hide()
            self._project_label.hide()
            self.layout().setContentsMargins(px(8), 0, 0, 0)
        else:
            self._back_button.show()
            self._project_icon.show()
            self._project_label.show()
            self._project_label.setText(messenger.get_project())
            self.layout().setContentsMargins(0, 0, 0, 0)

        self._page_name_label.setText(page_name)


class StatusBar(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(StatusBar, self).__init__(parent)
        self._init_ui()
        self._init_layout()
        self._init_signals()

    def _init_ui(self):
        self.setFixedHeight(px(25))
        self._menu_button = QtWidgets.QToolButton(self)
        self._menu_button.setIcon(
            QtGui.QIcon(os.path.join(BD_RESOURCES_DIR, "icons", "toolbutton_settingsMenu.png"))
        )
        self._menu_button.setFocusPolicy(QtCore.Qt.NoFocus)
        self._menu_button.setFixedSize(self.height(), self.height())
        self._menu_button.setToolTip("Click to open Settings menu")

        self._menu_button.setStyleSheet("border: none")

    def _init_layout(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._menu_button, 0, QtCore.Qt.AlignRight)

    def _init_signals(self):
        self._menu_button.clicked.connect(messenger.settings_menu_activated.emit)


class Page1(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(Page1, self).__init__(parent)
        self.setObjectName("PROJECTS")
        self._init_ui()
        self._init_layout()
        self._init_signals()

    def _init_ui(self):
        self._view = ProjectsView(self)
        self._view.setModel(model_projects)

    def _init_layout(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(px(1.5), 0, px(1.5), 0)
        layout.addWidget(self._view)

    def _init_signals(self):
        self._view.activated.connect(self._on_view_item_activated)

    def _on_view_item_activated(self, index):
        messenger.project_selected.emit(index.data(QtCore.Qt.UserRole))


class Page2(Page1):

    def __init__(self, parent=None):
        super(Page2, self).__init__(parent)
        self.setObjectName("PRESETS")

    def _init_ui(self):
        self._view = PresetsView(self)
        self._view.setModel(model_presets)

    def _on_view_item_activated(self, index):
        messenger.preset_selected.emit(index.data(QtCore.Qt.UserRole))


class Page3(Page1):

    def __init__(self, parent=None):
        super(Page3, self).__init__(parent)
        self.setObjectName("LAUNCHERS")

    def _init_ui(self):
        self._view = LaunchersView(self)
        self._view.setModel(model_launchers)

    def _on_view_item_activated(self, index):
        messenger.launcher_selected.emit(index.data(QtCore.Qt.UserRole))


class MainWindow(QtWidgets.QWidget):

    cached_geo = None

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)

        self._init_ui()
        self._init_layout()
        self._init_signals()

    def _init_ui(self):
        self.setWindowFlags(self.windowFlags() & QtCore.Qt.Popup)

        icon = QtGui.QIcon(APP_ICON)
        self.setWindowIcon(icon)
        self.setWindowTitle("BD Pipeline Desktop{}".format("" if not BD_DEVEL else " - DEV"))

        self._stacked_widget = QtWidgets.QStackedWidget(self)

        self._page_1 = Page1(self._stacked_widget)
        self._page_2 = Page2(self._stacked_widget)
        self._page_3 = Page3(self._stacked_widget)

        self._stacked_widget.addWidget(self._page_1)
        self._stacked_widget.addWidget(self._page_2)
        self._stacked_widget.addWidget(self._page_3)

        self._navbar = NavigationBar(self)
        self._navbar.update(self._page_1.objectName(), 0)

        self._statusbar = StatusBar(self)

        self._settings_menu = QtWidgets.QMenu(self)
        self._settings_menu.addAction("Exit", on_exit_clicked)
        self._settings_menu.setMinimumWidth(px(100))

    def _init_layout(self):
        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._main_layout.setSpacing(0)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.addWidget(self._navbar)
        self._main_layout.addWidget(self._stacked_widget)
        self._main_layout.addWidget(self._statusbar)

    def _init_signals(self):
        self._navbar.back_button_clicked.connect(
            lambda: self._stacked_widget.setCurrentIndex(
                max(0, self._stacked_widget.currentIndex()-1)
            )
        )
        self._stacked_widget.currentChanged.connect(self._on_page_changed)
        messenger.project_selected.connect(self._on_project_selected)
        messenger.preset_selected.connect(self._on_preset_selected)
        messenger.settings_menu_activated.connect(self._on_settings_menu_activated)

    def _on_settings_menu_activated(self):
        pos = QtGui.QCursor.pos()
        self._settings_menu.popup(pos)

    def _on_page_changed(self, index):
        page_name = self._stacked_widget.widget(index).objectName()
        self._navbar.update(page_name, index)

    def _on_project_selected(self):
        next_page_index = 1
        self._stacked_widget.setCurrentIndex(next_page_index)

    def _on_preset_selected(self):
        next_page_index = 2
        self._stacked_widget.setCurrentIndex(next_page_index)

    def closeEvent(self, event):
        MainWindow.cached_geo = self.geometry()
        event.ignore()
        self.hide()


class SystemTrayIcon(QtWidgets.QSystemTrayIcon):

    def __init__(self, widget, parent=None):
        super(SystemTrayIcon, self).__init__(parent)
        self._widget = widget
        self._init_ui()
        self._init_signals()

    def _init_ui(self):
        icon = QtGui.QIcon(APP_ICON)
        self.setIcon(icon)
        self.setToolTip("BD Pipeline Desktop")
        self._add_context_menu()

    def _init_signals(self):
        self.activated.connect(self.on_activated)

    def _add_context_menu(self):
        menu = QtWidgets.QMenu()
        menu.setMinimumWidth(px(100))
        menu.addAction("Exit", on_exit_clicked)
        self.setContextMenu(menu)

    def on_activated(self, reason):
        if reason != self.Context:

            if self._widget.isHidden():

                if MainWindow.cached_geo:
                    self._widget.setGeometry(MainWindow.cached_geo)

                self._widget.showNormal()
                self._widget.activateWindow()
                self._widget.raise_()

            else:
                MainWindow.cached_geo = self._widget.geometry()
                self._widget.hide()

    def on_singleton_activated(self):
        if self._widget.isHidden():

            if MainWindow.cached_geo:
                self._widget.setGeometry(MainWindow.cached_geo)

            self._widget.showNormal()

        self._widget.activateWindow()
        self._widget.raise_()


@QtCore.Slot()
def on_exit_clicked():
    button = QtWidgets.QMessageBox.question(None,
                                       "BD Pipeline Desktop Message",
                                       "Are you sure you want to exit?",
                                       QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                       QtWidgets.QMessageBox.Yes)
    if button == QtWidgets.QMessageBox.Yes:
        ApplicationSingleton.instance().quit()


def get_project_infos():
    import yaml

    preset_root_dir = os.path.join(BD_PIPELINE_DIR, "presets")

    project_infos = []
    project_infos_map = {}

    for preset_name in os.listdir(preset_root_dir):

        preset_dir = os.path.join(preset_root_dir, preset_name)

        config = os.path.join(preset_dir, "config", "preset.yml")
        if not os.path.exists(config):
            continue

        with open(config, "r") as f:
            data = yaml.load(f)
            proj_name = data.get("project")

        project_info = project_infos_map.get(proj_name)

        if not project_info:
            project_info = {
                "name": proj_name,
                "presets": [preset_name]
            }
            project_infos_map[proj_name] = project_info
            project_infos.append(project_info)
            continue

        project_info["presets"].append(preset_name)

    return project_infos


def get_launcher_infos(preset_name):

    os.environ["BD_PRESET_NAME"] = preset_name
    os.environ["BD_OS"] = bd.config.CURRENT_PLATFORM

    config = bd.config.loader.Loader.load()

    del os.environ["BD_PRESET_NAME"]
    del os.environ["BD_OS"]

    launcher_infos = []

    for launcher_name, launcher_data in config.get("launchers").iteritems():

        launcher_info = {"launcher_name": launcher_name, "versions": [], "active_version": None}

        icon_filename = os.path.join(
            config.get("proj_preset_dir"),
            "resources",
            "icons",
            "launcher_{name}.png".format(name=launcher_name)
        )

        if not os.path.exists(icon_filename):
            icon_filename = os.path.join(
                BD_PIPELINE_DIR,
                "resources",
                "icons",
                "launcher_{name}.png".format(name=launcher_name)
            )
            if not os.path.exists(icon_filename):
                icon_filename = LAUNCHER_ICON

        launcher_info["icon_filename"] = icon_filename

        for version in launcher_data.iterkeys():

            if version == "default":
                continue

            launcher_info["versions"].append(version)

        active_version = launcher_data.get("default", launcher_info["versions"][-1])
        launcher_info["active_version"] = active_version
        launcher_infos.append(launcher_info)

    return launcher_infos


@QtCore.Slot(dict)
def on_project_selected(project_info):
    messenger.preset_infos_ready.emit([{"name": preset} for preset in project_info["presets"]])


@QtCore.Slot(dict)
def on_preset_selected(preset_info):
    launcher_infos = get_launcher_infos(preset_info["name"])
    messenger.launcher_infos_ready.emit(launcher_infos)


@QtCore.Slot(dict)
def on_launcher_selected(launcher_info):
    process = QtCore.QProcess()

    process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
    process.readyReadStandardOutput.connect(lambda: on_process_output(process))

    command = \
        ("{pipeline_dir}/bin/activate bd -p {preset}"
         " launch {launcher_name} -v {launcher_version}").format(
             pipeline_dir=str(BD_PIPELINE_DIR),
             preset=str(messenger.get_preset()),
             launcher_name=str(launcher_info["launcher_name"]),
             launcher_version=str(launcher_info["active_version"])
        )
    LOGGER.info("Executing command: {}".format(command))

    process.start(command)


@QtCore.Slot(QtCore.QProcess)
def on_process_output(process):
    print process.readAll(),


#
# model access protocols
#

def model_protocol_projects(role, index, data):
    row = index.row()
    if role == QtCore.Qt.DisplayRole:
        return "  " + data[row]["name"]
    elif role == QtCore.Qt.DecorationRole:
        return QtGui.QIcon(PROJECT_ICON)
    elif role == QtCore.Qt.UserRole:
        return data[row]


def model_protocol_presets(role, index, data):
    row = index.row()
    if role == QtCore.Qt.DisplayRole:
        return "  " + data[row]["name"]
    elif role == QtCore.Qt.DecorationRole:
        return QtGui.QIcon(PRESET_ICON)
    elif role == QtCore.Qt.UserRole:
        return data[row]


def model_protocol_launchers(role, index, data):
    row = index.row()
    col = index.column()
    if role == QtCore.Qt.DisplayRole:
        if col == 0:
            return "  " + data[row]["launcher_name"].title()
        else:
            return data[row]["active_version"]
    elif role == QtCore.Qt.DecorationRole:
        if col == 0:
            launcher_icon = data[row]["icon_filename"]
            return QtGui.QIcon(launcher_icon)
    elif role == QtCore.Qt.ToolTipRole:
        if col == 1:
            return "Click to choose the application version to run"
    elif role == QtCore.Qt.UserRole:
        return data[row]


class ApplicationSingleton(QtWidgets.QApplication):

    activated = QtCore.Signal()

    def __init__(self, id, *argv):
        super(ApplicationSingleton, self).__init__(*argv)

        self._id = id

        self._out_socket = QtNetwork.QLocalSocket()
        self._out_socket.connectToServer(self._id)
        self._is_running = self._out_socket.waitForConnected()

        if not self._is_running:
            self._out_socket = None
            self._server = QtNetwork.QLocalServer()
            self._server.listen(self._id)
            self._server.newConnection.connect(self._on_new_connection)

    def is_running(self):
        return self._is_running

    def id(self):
        return self._id

    def _on_new_connection(self):
        self.activated.emit()


def _add_args(parser):
    parser.add_argument("-u", "--user", type=str,
                        help="Run as a specific user")


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])

    import qdarkstyle
    import warnings

    logging.basicConfig(level=logging.INFO)

    parser = ArgumentParser(prog="bd-desktop")

    _add_args(parser)

    args = parser.parse_args()

    user = os.getenv("BD_USER", getpass.getuser())
    os.environ["BD_USER"] = args.user if args.user else user

    app_guid = '87a2876e-7c5e-4688-9560-11f897f556d3'

    app = ApplicationSingleton(app_guid, sys.argv)

    if app.is_running():
        sys.exit(0)

    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        app.setStyleSheet(qdarkstyle.load_stylesheet_pyside2())

    model_projects = ItemModel(model_protocol_projects)
    messenger.project_infos_ready.connect(model_projects.update)

    model_presets = ItemModel(model_protocol_presets)
    messenger.preset_infos_ready.connect(model_presets.update)

    model_launchers = ItemModel(model_protocol_launchers, 2, 1)
    messenger.launcher_infos_ready.connect(model_launchers.update)

    messenger.project_selected.connect(on_project_selected)
    messenger.preset_selected.connect(on_preset_selected)
    messenger.launcher_selected.connect(on_launcher_selected)

    main_window = MainWindow()

    screen_geo = app.desktop().availableGeometry(app.desktop().primaryScreen())
    screen_geo.setTop(screen_geo.bottom() - px(300))
    screen_geo.setLeft(screen_geo.right() - px(220))

    main_window.setGeometry(screen_geo)

    main_window.setMinimumWidth(screen_geo.width())

    main_window.show()

    tray_icon = SystemTrayIcon(main_window)
    tray_icon.show()

    project_infos = get_project_infos()
    messenger.project_infos_ready.emit(project_infos)

    app.activated.connect(tray_icon.on_singleton_activated)

    sys.exit(app.exec_())