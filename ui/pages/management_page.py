"""
Management page.

Two-column layout:
  Left  — list of all instances; selecting one populates the right side
  Right — three stacked panels for the selected instance:
            * Resources (allocated + live usage)
            * Networking (host/container ports + container status)
            * Audit log (last N events)

The page polls live container stats while an instance is selected and
running; the poller is torn down when the user picks a different
instance or leaves the page.
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QFrame, QStackedWidget, QGridLayout, QProgressBar, QTextEdit, QSizePolicy,
)

from ui.pages.base_page import BasePage
from instances import Instance, get_store
from instances.models import InstanceStatus
from runtime.audit import get_audit_log, AuditEvent
from runtime.docker_backend import (
    get_backend, ContainerStats, DockerNotAvailable, DockerError,
)
from runtime.workers import StatsPoller
from vulnerabilities import Category, get_vulnerability


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_bytes(n: float) -> str:
    """Pretty-print a byte count: 1024 → '1.0 KB', etc."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _fmt_ts(iso: str) -> str:
    """Render an ISO-8601 UTC timestamp as HH:MM:SS local-ish (just trim)."""
    try:
        dt = datetime.fromisoformat(iso.rstrip("Z"))
        return dt.strftime("%H:%M:%S")
    except ValueError:
        return iso


# ---------------------------------------------------------------------------
# Detail panels
# ---------------------------------------------------------------------------

class ResourcesPanel(QFrame):
    """Allocated vs live usage."""

    def __init__(self):
        super().__init__()
        self.setObjectName("mgmtPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Resources")
        title.setObjectName("mgmtPanelTitle")
        layout.addWidget(title)

        # CPU section
        self._cpu_alloc_label = QLabel()
        self._cpu_alloc_label.setObjectName("mgmtFieldValue")

        self._cpu_bar = QProgressBar()
        self._cpu_bar.setRange(0, 100)
        self._cpu_bar.setValue(0)
        self._cpu_bar.setObjectName("mgmtProgressBar")
        self._cpu_bar.setFormat("%v%")

        self._cpu_live_label = QLabel("idle")
        self._cpu_live_label.setObjectName("mgmtFieldHint")

        # Memory section
        self._mem_alloc_label = QLabel()
        self._mem_alloc_label.setObjectName("mgmtFieldValue")

        self._mem_bar = QProgressBar()
        self._mem_bar.setRange(0, 100)
        self._mem_bar.setValue(0)
        self._mem_bar.setObjectName("mgmtProgressBar")
        self._mem_bar.setFormat("%v%")

        self._mem_live_label = QLabel("idle")
        self._mem_live_label.setObjectName("mgmtFieldHint")

        # PIDs / cores
        self._pids_label = QLabel("—")
        self._pids_label.setObjectName("mgmtFieldValue")

        # Build the grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)

        grid.addWidget(self._kv_label("CPU allocated"),  0, 0)
        grid.addWidget(self._cpu_alloc_label,            0, 1)

        grid.addWidget(self._kv_label("CPU usage"),      1, 0)
        grid.addWidget(self._cpu_bar,                    1, 1)
        grid.addWidget(self._cpu_live_label,             2, 1)

        grid.addWidget(self._kv_label("Memory allocated"), 3, 0)
        grid.addWidget(self._mem_alloc_label,              3, 1)

        grid.addWidget(self._kv_label("Memory usage"),   4, 0)
        grid.addWidget(self._mem_bar,                    4, 1)
        grid.addWidget(self._mem_live_label,             5, 1)

        grid.addWidget(self._kv_label("Processes"),      6, 0)
        grid.addWidget(self._pids_label,                 6, 1)

        layout.addLayout(grid)

    @staticmethod
    def _kv_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("mgmtFieldKey")
        return lbl

    def show_for(self, instance: Instance):
        self._cpu_alloc_label.setText(f"{instance.resources.cpu_cores} cores")
        self._mem_alloc_label.setText(f"{instance.resources.memory_mb} MB")
        # Live values cleared until poller produces something.
        self.update_stats(None)

    def update_stats(self, stats: ContainerStats | None):
        if stats is None:
            self._cpu_bar.setValue(0)
            self._cpu_live_label.setText("not running")
            self._mem_bar.setValue(0)
            self._mem_live_label.setText("not running")
            self._pids_label.setText("—")
            return

        cpu_pct = max(0.0, min(100.0, stats.cpu_percent))
        self._cpu_bar.setValue(int(cpu_pct))
        self._cpu_live_label.setText(
            f"{cpu_pct:.1f}% across {stats.online_cpus} online CPU(s)"
        )

        mem_pct = max(0.0, min(100.0, stats.memory_percent))
        self._mem_bar.setValue(int(mem_pct))
        self._mem_live_label.setText(
            f"{stats.memory_mb:.1f} MB / {stats.memory_limit_mb:.0f} MB ({mem_pct:.1f}%)"
        )

        self._pids_label.setText(str(stats.pids))


class NetworkingPanel(QFrame):
    """Port mappings + live container status + network I/O."""

    def __init__(self):
        super().__init__()
        self.setObjectName("mgmtPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Networking")
        title.setObjectName("mgmtPanelTitle")
        layout.addWidget(title)

        self._status_label = QLabel("—")
        self._status_label.setObjectName("mgmtFieldValue")

        self._ports_label = QLabel("—")
        self._ports_label.setObjectName("mgmtFieldValue")
        self._ports_label.setWordWrap(True)
        self._ports_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._rx_label = QLabel("—")
        self._rx_label.setObjectName("mgmtFieldValue")

        self._tx_label = QLabel("—")
        self._tx_label.setObjectName("mgmtFieldValue")

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)
        grid.addWidget(self._kv_label("Container status"), 0, 0)
        grid.addWidget(self._status_label,                 0, 1)
        grid.addWidget(self._kv_label("Port mappings"),    1, 0)
        grid.addWidget(self._ports_label,                  1, 1)
        grid.addWidget(self._kv_label("Network RX"),       2, 0)
        grid.addWidget(self._rx_label,                     2, 1)
        grid.addWidget(self._kv_label("Network TX"),       3, 0)
        grid.addWidget(self._tx_label,                     3, 1)

        layout.addLayout(grid)

    @staticmethod
    def _kv_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("mgmtFieldKey")
        return lbl

    def show_for(self, instance: Instance):
        if instance.resources.port_mappings:
            self._ports_label.setText(", ".join(
                f"localhost:{h} → container:{c}"
                for h, c in instance.resources.port_mappings
            ))
        else:
            self._ports_label.setText("no service ports — challenge is offline-only")

        # Status / IO will be filled by update_status / update_stats.
        self._status_label.setText(instance.status.display_name)
        self._rx_label.setText("—")
        self._tx_label.setText("—")

    def update_status(self, container_status: str):
        self._status_label.setText(container_status)

    def update_stats(self, stats: ContainerStats | None):
        if stats is None:
            self._rx_label.setText("—")
            self._tx_label.setText("—")
            return
        self._rx_label.setText(_fmt_bytes(stats.network_rx))
        self._tx_label.setText(_fmt_bytes(stats.network_tx))


class AuditPanel(QFrame):
    """Tail of the audit log for the selected instance."""

    MAX_LINES = 500

    def __init__(self):
        super().__init__()
        self.setObjectName("mgmtPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Audit log")
        title.setObjectName("mgmtPanelTitle")
        layout.addWidget(title)

        self._log_view = QTextEdit()
        self._log_view.setObjectName("mgmtAuditLog")
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self._log_view)

        self._instance_id: str | None = None

        get_audit_log().event_recorded.connect(self._on_event)

    def show_for(self, instance: Instance):
        self._instance_id = instance.id
        events = get_audit_log().read(instance.working_dir, tail=self.MAX_LINES)
        # If there are no events yet (first time), seed with a CREATED line.
        if not events:
            self._log_view.setPlainText(
                f"[{_fmt_ts(instance.created_at)}]  created  · {instance.name} created from template"
            )
        else:
            self._log_view.setPlainText("\n".join(self._format(e) for e in events))
        # Scroll to bottom
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear(self):
        self._instance_id = None
        self._log_view.clear()

    def _on_event(self, event: AuditEvent):
        if event.instance_id != self._instance_id:
            return
        self._log_view.append(self._format(event))
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    @staticmethod
    def _format(event: AuditEvent) -> str:
        return f"[{_fmt_ts(event.timestamp)}]  {event.kind:<14}· {event.message}"


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

class ManagementPage(BasePage):
    POLL_INTERVAL_MS = 2000

    def __init__(self):
        super().__init__(
            title="Management",
            subtitle="Inspect a deployed instance: resources, networking, and audit history."
        )

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(16)

        # ---- Left: instance picker ----
        left_col = QVBoxLayout()
        left_col.setSpacing(6)

        picker_label = QLabel("Active instances")
        picker_label.setObjectName("mgmtSectionHeader")
        left_col.addWidget(picker_label)

        self._instance_list = QListWidget()
        self._instance_list.setObjectName("mgmtInstanceList")
        self._instance_list.setMinimumWidth(220)
        self._instance_list.setMaximumWidth(280)
        self._instance_list.currentItemChanged.connect(self._on_picker_changed)
        left_col.addWidget(self._instance_list, stretch=1)

        body_layout.addLayout(left_col)

        # ---- Right: detail stack ----
        self._detail_stack = QStackedWidget()
        self._detail_stack.addWidget(self._build_empty_state())   # 0
        self._detail_stack.addWidget(self._build_detail_view())   # 1
        body_layout.addWidget(self._detail_stack, stretch=1)

        self.add_content(body, stretch=1)

        # State
        self._selected_id: str | None = None
        self._poller: StatsPoller | None = None

        # Timer for occasional container-status checks (cheaper than stats)
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(3000)
        self._status_timer.timeout.connect(self._refresh_container_status)

        # Wire to the store
        store = get_store()
        store.instance_added.connect(lambda _: self._refresh_picker())
        store.instance_removed.connect(lambda _: self._refresh_picker())
        store.instance_updated.connect(lambda _: self._refresh_picker())
        store.catalog_reloaded.connect(self._refresh_picker)

        self._refresh_picker()

    # ------------------------------------------------------------------
    # Right-side builders
    # ------------------------------------------------------------------

    def _build_empty_state(self) -> QWidget:
        empty = QWidget()
        layout = QVBoxLayout(empty)
        layout.setContentsMargins(0, 60, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("No instance selected")
        title.setObjectName("emptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("Pick one from the list on the left to inspect.")
        hint.setObjectName("placeholderText")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addSpacing(6)
        layout.addWidget(hint)
        return empty

    def _build_detail_view(self) -> QWidget:
        scroll_holder = QWidget()
        layout = QVBoxLayout(scroll_holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Top header strip with name + template
        self._detail_header = QLabel()
        self._detail_header.setObjectName("mgmtDetailHeader")
        self._detail_header.setWordWrap(True)
        layout.addWidget(self._detail_header)

        # Three panels stacked vertically
        self._resources_panel  = ResourcesPanel()
        self._networking_panel = NetworkingPanel()
        self._audit_panel      = AuditPanel()

        # Resources + Networking side by side; audit log full width below.
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        top_row.addWidget(self._resources_panel,  stretch=1)
        top_row.addWidget(self._networking_panel, stretch=1)
        layout.addLayout(top_row)

        layout.addWidget(self._audit_panel, stretch=1)

        return scroll_holder

    # ------------------------------------------------------------------
    # Picker
    # ------------------------------------------------------------------

    def _refresh_picker(self):
        # Preserve selection if possible
        previous = self._selected_id

        self._instance_list.blockSignals(True)
        self._instance_list.clear()
        for inst in get_store().all():
            item = QListWidgetItem(self._format_picker_row(inst))
            item.setData(Qt.ItemDataRole.UserRole, inst.id)
            self._instance_list.addItem(item)
        self._instance_list.blockSignals(False)

        # Restore selection if the previously-selected instance still exists.
        if previous is not None:
            for i in range(self._instance_list.count()):
                if self._instance_list.item(i).data(Qt.ItemDataRole.UserRole) == previous:
                    self._instance_list.setCurrentRow(i)
                    return

        # Nothing selected -> empty state
        self._selected_id = None
        self._stop_polling()
        self._detail_stack.setCurrentIndex(0)

    @staticmethod
    def _format_picker_row(instance: Instance) -> str:
        return f"  {instance.name}\n    {instance.status.display_name}"

    def _on_picker_changed(self, current: QListWidgetItem | None, _prev):
        if current is None:
            self._selected_id = None
            self._stop_polling()
            self._detail_stack.setCurrentIndex(0)
            return

        instance_id = current.data(Qt.ItemDataRole.UserRole)
        if instance_id == self._selected_id:
            return

        self._selected_id = instance_id
        inst = get_store().get(instance_id)
        if inst is None:
            self._detail_stack.setCurrentIndex(0)
            return

        # Header line: name · template · category badge
        tmpl = get_vulnerability(inst.template_id)
        try:
            cat_display = Category(inst.category).display_name
        except ValueError:
            cat_display = inst.category
        self._detail_header.setText(
            f"<b>{inst.name}</b>  ·  {tmpl.name if tmpl else inst.template_id}  ·  {cat_display}"
            f"<br><span style='color:#9ca3af; font-size:11px;'>id: {inst.id}</span>"
        )

        self._resources_panel.show_for(inst)
        self._networking_panel.show_for(inst)
        self._audit_panel.show_for(inst)
        self._detail_stack.setCurrentIndex(1)

        # Kick off live polling + status checks
        self._start_polling()
        self._refresh_container_status()

    # ------------------------------------------------------------------
    # Live polling
    # ------------------------------------------------------------------

    def _start_polling(self):
        self._stop_polling()
        if self._selected_id is None:
            return
        inst = get_store().get(self._selected_id)
        if inst is None:
            return

        # Stats poller (only emits while container is running)
        self._poller = StatsPoller(inst, interval_ms=self.POLL_INTERVAL_MS, parent=self)
        self._poller.stats_ready.connect(self._on_stats_ready)
        self._poller.error.connect(self._on_poller_error)
        self._poller.start()

        # Periodic container-status check
        self._status_timer.start()

    def _stop_polling(self):
        if self._poller is not None:
            self._poller.stop()
            # Don't .wait() — UI thread; let it exit on its own.
            self._poller = None
        if self._status_timer.isActive():
            self._status_timer.stop()

    def _on_stats_ready(self, stats: ContainerStats):
        self._resources_panel.update_stats(stats)
        self._networking_panel.update_stats(stats)

    def _on_poller_error(self, msg: str):
        # Most likely Docker isn't running; we already surfaced this elsewhere.
        # Just clear the live view.
        self._resources_panel.update_stats(None)
        self._networking_panel.update_stats(None)

    def _refresh_container_status(self):
        if self._selected_id is None:
            return
        inst = get_store().get(self._selected_id)
        if inst is None:
            return
        try:
            status = get_backend().status(inst)
        except (DockerNotAvailable, DockerError):
            status = "unavailable"
        self._networking_panel.update_status(status)