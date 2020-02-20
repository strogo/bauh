import operator
import time
from functools import reduce

from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy, QTableWidget, QHeaderView

from bauh.api.abstract.controller import SoftwareManager
from bauh.api.abstract.handler import TaskManager
from bauh.view.util.translation import I18n


class Prepare(QThread, TaskManager):
    signal_register = pyqtSignal(str, str, object)
    signal_update = pyqtSignal(str, float, str)
    signal_finished = pyqtSignal(str)

    def __init__(self, manager: SoftwareManager):
        super(Prepare, self).__init__()
        self.manager = manager

    def run(self):
        root_pwd = None
        if self.manager.requires_root('prepare', None):
            root_pwd = None  # TODO

        self.manager.prepare(self, root_pwd)

    def update_progress(self, task_id: str, progress: float, substatus: str):
        self.signal_update.emit(task_id, progress, substatus)

    def register_task(self, id_: str, label: str, icon_path: str):
        self.signal_register.emit(id_, label, icon_path)

    def finish_task(self, task_id: str):
        self.signal_finished.emit(task_id)


class CheckFinished(QThread):
    signal_finished = pyqtSignal()

    def __init__(self):
        super(CheckFinished, self).__init__()
        self.total = None
        self.finished = None

    def run(self):
        while True:
            if self.total is not None and self.finished is not None:
                if self.total == self.finished:
                    break

            time.sleep(0.01)

        time.sleep(2)
        self.signal_finished.emit()

    def update(self, total: int, finished: int):
        if total is not None:
            self.total = total

        if finished is not None:
            self.finished = finished


class PreparePanel(QWidget, TaskManager):

    signal_status = pyqtSignal(object, object)

    def __init__(self, manager: SoftwareManager, screen_size: QSize,  i18n: I18n, manage_window: QWidget):
        super(PreparePanel, self).__init__()
        # self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.i18n = i18n
        self.manage_window = manage_window
        self.setWindowTitle(' ')
        self.setMinimumWidth(screen_size.width() * 0.5)
        self.setMinimumHeight(screen_size.height() * 0.35)
        self.setLayout(QVBoxLayout())
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.manager = manager
        self.tasks = {}
        self.ntasks = 0
        self.ftasks = 0

        self.prepare_thread = Prepare(manager)
        self.prepare_thread.signal_register.connect(self.register_task)
        self.prepare_thread.signal_update.connect(self.update_progress)
        self.prepare_thread.signal_finished.connect(self.finish_task)

        self.check_thread = CheckFinished()
        self.signal_status.connect(self.check_thread.update)
        self.check_thread.signal_finished.connect(self.finish)

        self.label_top = QLabel()
        self.label_top.setText("... Initializing ...")
        self.label_top.setAlignment(Qt.AlignHCenter)
        self.label_top.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; }")
        self.layout().addWidget(self.label_top)
        self.layout().addWidget(QLabel())

        self.table = QTableWidget()
        self.table.setStyleSheet("QTableWidget { background-color: transparent; }")
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setVisible(False)
        self.table.horizontalHeader().setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['' for _ in range(4)])
        self.layout().addWidget(self.table)

    def get_table_width(self) -> int:
        return reduce(operator.add, [self.table.columnWidth(i) for i in range(self.table.columnCount())])

    def _resize_columns(self):
        header_horizontal = self.table.horizontalHeader()
        for i in range(self.table.columnCount()):
            header_horizontal.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.resize(self.get_table_width() * 1.05, self.height())

    def show(self):
        super(PreparePanel, self).show()
        self.check_thread.start()
        self.prepare_thread.start()

    def register_task(self, id_: str, label: str, icon_path: str):
        self.ntasks += 1
        self.table.setRowCount(self.ntasks)

        task_row = self.ntasks - 1

        lb_icon = QLabel()
        lb_icon.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

        if icon_path:
            lb_icon.setPixmap(QIcon(icon_path).pixmap(12, 12))
            lb_icon.setAlignment(Qt.AlignHCenter)

        self.table.setCellWidget(task_row, 0, lb_icon)

        lb_status = QLabel(label)
        lb_status.setContentsMargins(2, 2, 2, 2)
        lb_status.setMinimumWidth(50)
        lb_status.setAlignment(Qt.AlignHCenter)
        lb_status.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        lb_status.setStyleSheet("QLabel { color: blue; font-weight: bold; }")
        self.table.setCellWidget(task_row, 1, lb_status)

        lb_sub = QLabel()
        lb_sub.setContentsMargins(2, 2, 2, 2)
        lb_sub.setAlignment(Qt.AlignHCenter)
        lb_sub.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        lb_sub.setMinimumWidth(50)
        self.table.setCellWidget(task_row, 2, lb_sub)

        lb_progress = QLabel('{0:.2f}'.format(0) + '%')
        lb_progress.setContentsMargins(2, 2, 2, 2)
        lb_progress.setStyleSheet("QLabel { color: blue; font-weight: bold; }")
        lb_progress.setAlignment(Qt.AlignHCenter)
        lb_progress.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

        self.table.setCellWidget(task_row, 3, lb_progress)

        self.tasks[id_] = {'lb_status': lb_status,
                           'lb_prog': lb_progress,
                           'progress': 0,
                           'lb_sub': lb_sub,
                           'finished': False}

        self.signal_status.emit(self.ntasks, self.ftasks)

    def update_progress(self, task_id: str, progress: float, substatus: str):
        task = self.tasks[task_id]

        if progress != task['progress']:
            task['progress'] = progress
            task['lb_prog'].setText('{0:.2f}'.format(progress) + '%')

        if substatus:
            task['lb_sub'].setText('( {} )'.format(substatus))
        else:
            task['lb_sub'].setText('')

        self._resize_columns()

    def finish_task(self, task_id: str):
        task = self.tasks[task_id]
        task['lb_sub'].setText('')

        for key in ('lb_prog', 'lb_status'):
            task[key].setStyleSheet('QLabel { color: green; text-decoration: line-through; }')

        task['finished'] = True
        self._resize_columns()

        self.ftasks += 1
        self.signal_status.emit(self.ntasks, self.ftasks)

        if self.ntasks == self.ftasks:
            self.label_top.setText("... Ready ...")

    def finish(self):
        self.manage_window.refresh_apps()
        self.manage_window.show()
        self.close()
