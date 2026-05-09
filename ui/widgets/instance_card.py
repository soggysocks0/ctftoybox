"""
InstanceCard — a single row in the instance list.

Shows the instance's name, category badge, status pill, ports, and the
two primary actions: Run / Stop. Action buttons emit signals; the
backend wiring (actually running docker) lands in a later task.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame,
    QSizePolicy,
)

from instances import Instance, InstanceStatus
from vulnerabilities import Category, get_vulnerability


# Map status -> the QSS objectName we'll style the pill with.
_STATUS_OBJECT_NAME = {
    InstanceStatus.GENERATED: "statusPillGenerated",
    InstanceStatus.BUILDING:  "statusPillBuilding",
    InstanceStatus.STOPPED:   "statusPillStopped",
    InstanceStatus.RUNNING:   "statusPillRunning",
    InstanceStatus.ERROR:     "statusPillError",
}


class InstanceCard(QFrame):
    """Visual card representing one Instance."""

    run_clicked    = pyqtSignal(str)  # emits instance id
    stop_clicked   = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)
    open_clicked   = pyqtSignal(str)  # "open folder" / inspect

    def __init__(self, instance: Instance, parent=None):
        super().__init__(parent)
        self.setObjectName("instanceCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._instance = instance

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(96)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(14)

        # ----- Left: name + meta -----
        left = QVBoxLayout()
        left.setSpacing(4)

        # Header row (name + category + status pill)
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self._name_label = QLabel(instance.name)
        self._name_label.setObjectName("instanceCardName")

        self._category_label = QLabel(self._category_display(instance.category))
        self._category_label.setObjectName("instanceCardCategory")

        self._status_pill = QLabel()
        self._set_status_pill(instance.status)

        header_row.addWidget(self._name_label)
        header_row.addWidget(self._category_label)
        header_row.addSpacing(4)
        header_row.addWidget(self._status_pill)
        header_row.addStretch()

        left.addLayout(header_row)

        # Subline: template + resources + ports
        self._sub_label = QLabel(self._build_sub_text(instance))
        self._sub_label.setObjectName("instanceCardSub")
        self._sub_label.setWordWrap(True)
        left.addWidget(self._sub_label)

        # Tertiary: instance id (small, monospaced-ish)
        self._id_label = QLabel(f"id: {instance.id}")
        self._id_label.setObjectName("instanceCardId")
        left.addWidget(self._id_label)

        outer.addLayout(left, stretch=1)

        # ----- Right: actions -----
        actions = QHBoxLayout()
        actions.setSpacing(6)

        self._run_btn = QPushButton("▶  Run")
        self._run_btn.setObjectName("cardActionPrimary")
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.clicked.connect(lambda: self.run_clicked.emit(self._instance.id))

        self._stop_btn = QPushButton("■  Stop")
        self._stop_btn.setObjectName("cardActionSecondary")
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.clicked.connect(lambda: self.stop_clicked.emit(self._instance.id))

        self._open_btn = QPushButton("Open folder")
        self._open_btn.setObjectName("cardActionGhost")
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.clicked.connect(lambda: self.open_clicked.emit(self._instance.id))

        self._delete_btn = QPushButton("✕")
        self._delete_btn.setObjectName("cardActionDanger")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setToolTip("Delete instance and remove generated files")
        self._delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self._instance.id))

        actions.addWidget(self._open_btn)
        actions.addWidget(self._run_btn)
        actions.addWidget(self._stop_btn)
        actions.addWidget(self._delete_btn)

        outer.addLayout(actions)

        self._refresh_action_state()

    # ------------------------------------------------------------------
    # Public update API
    # ------------------------------------------------------------------

    def update_from(self, instance: Instance):
        """Re-render this card to reflect the given (presumably newer) Instance."""
        self._instance = instance
        self._name_label.setText(instance.name)
        self._category_label.setText(self._category_display(instance.category))
        self._sub_label.setText(self._build_sub_text(instance))
        self._id_label.setText(f"id: {instance.id}")
        self._set_status_pill(instance.status)
        self._refresh_action_state()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _set_status_pill(self, status: InstanceStatus):
        self._status_pill.setText(f"  {status.display_name}  ")
        self._status_pill.setObjectName(_STATUS_OBJECT_NAME.get(status, "statusPillGenerated"))
        # Force re-style
        self._status_pill.style().unpolish(self._status_pill)
        self._status_pill.style().polish(self._status_pill)

    def _refresh_action_state(self):
        running = self._instance.status == InstanceStatus.RUNNING
        building = self._instance.status == InstanceStatus.BUILDING
        self._run_btn.setEnabled(not running and not building)
        self._stop_btn.setEnabled(running)

    @staticmethod
    def _category_display(value: str) -> str:
        try:
            return Category(value).display_name
        except ValueError:
            return value

    @staticmethod
    def _build_sub_text(instance: Instance) -> str:
        tmpl = get_vulnerability(instance.template_id)
        tmpl_name = tmpl.name if tmpl else instance.template_id

        parts = [
            tmpl_name,
            f"{instance.resources.cpu_cores} CPU",
            f"{instance.resources.memory_mb} MB",
        ]
        if instance.resources.port_mappings:
            ports = ", ".join(
                f"{h}→{c}" for h, c in instance.resources.port_mappings
            )
            parts.append(f"ports {ports}")
        return "  ·  ".join(parts)