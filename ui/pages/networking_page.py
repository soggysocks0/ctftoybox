"""
Networking page.

Per-instance summary of port mappings and routing. Refreshes when the
instance store changes; periodic timer re-checks live container status.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFrame, QScrollArea,
    QStackedWidget, QPushButton, QSizePolicy,
)

from ui.pages.base_page import BasePage
from instances import Instance, InstanceStatus, get_store
from runtime.docker_backend import (
    get_backend, DockerNotAvailable, DockerError,
)
from vulnerabilities import Category, get_vulnerability


# ---------------------------------------------------------------------------
# A row representing one instance's networking
# ---------------------------------------------------------------------------

class NetworkingRow(QFrame):
    """One card per instance, showing ports + container state + routing."""

    def __init__(self, instance: Instance):
        super().__init__()
        self.setObjectName("networkingRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._instance = instance

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(8)

        # ---- Header: name + status pill + category ----
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        name = QLabel(instance.name)
        name.setObjectName("instanceCardName")
        header_row.addWidget(name)

        try:
            cat_display = Category(instance.category).display_name
        except ValueError:
            cat_display = instance.category
        cat_badge = QLabel(cat_display)
        cat_badge.setObjectName("instanceCardCategory")
        header_row.addWidget(cat_badge)

        self._status_pill = QLabel("…")
        self._status_pill.setObjectName("statusPillStopped")
        header_row.addWidget(self._status_pill)
        header_row.addStretch()

        outer.addLayout(header_row)

        # Sub-line: template + instance id
        tmpl = get_vulnerability(instance.template_id)
        sub = QLabel(
            f"{tmpl.name if tmpl else instance.template_id}  ·  id: {instance.id}"
        )
        sub.setObjectName("networkingRowSub")
        outer.addWidget(sub)

        # ---- Body: port table + routing notes ----
        body = QHBoxLayout()
        body.setSpacing(20)

        # Port mappings — left
        ports_col = QVBoxLayout()
        ports_col.setSpacing(2)
        ports_header = QLabel("Port mappings")
        ports_header.setObjectName("networkingFieldKey")
        ports_col.addWidget(ports_header)

        if instance.resources.port_mappings:
            for host_port, container_port in instance.resources.port_mappings:
                line = QLabel(
                    f"localhost:<b>{host_port}</b>  →  container:<b>{container_port}</b>  ·  TCP"
                )
                line.setObjectName("networkingFieldValue")
                line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                ports_col.addWidget(line)
        else:
            none_label = QLabel("no service ports — offline-only challenge")
            none_label.setObjectName("networkingFieldHint")
            ports_col.addWidget(none_label)

        body.addLayout(ports_col, stretch=2)

        # Routing — right
        routing_col = QVBoxLayout()
        routing_col.setSpacing(2)
        routing_header = QLabel("Routing")
        routing_header.setObjectName("networkingFieldKey")
        routing_col.addWidget(routing_header)

        # Compose the routing summary
        if instance.resources.port_mappings:
            for host_port, container_port in instance.resources.port_mappings:
                routing_col.addWidget(
                    self._make_routing_value(
                        f"client → host:{host_port} → docker0 → container:{container_port}"
                    )
                )
            extra = QLabel("Default Docker bridge network 'bridge'.")
            extra.setObjectName("networkingFieldHint")
            routing_col.addWidget(extra)
        else:
            offline = QLabel("Players retrieve a static artifact via "
                             "<code>docker cp</code> — no live routing.")
            offline.setObjectName("networkingFieldHint")
            offline.setWordWrap(True)
            routing_col.addWidget(offline)

        body.addLayout(routing_col, stretch=3)
        outer.addLayout(body)

        # Initial status from Instance.status (live refresh below replaces it)
        self.refresh_status_from_instance()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_routing_value(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("networkingFieldValue")
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return lbl

    def refresh_status_from_instance(self):
        """Fall back to the Instance.status when Docker isn't reachable."""
        status = self._instance.status
        self._set_status_pill(status.display_name, status.value)

    def refresh_from_docker_status(self, docker_status: str):
        """Update the pill from a fresh `docker ps`-style status string."""
        # Map docker statuses to our pill object names
        pill_obj = "statusPillStopped"
        label = docker_status
        if docker_status == "running":
            pill_obj = "statusPillRunning"
            label    = "Running"
        elif docker_status == "absent":
            pill_obj = "statusPillGenerated"
            label    = "Not built"
        elif docker_status in ("created",):
            pill_obj = "statusPillGenerated"
            label    = "Created"
        elif docker_status in ("exited", "dead"):
            pill_obj = "statusPillStopped"
            label    = "Stopped"
        elif docker_status == "unavailable":
            pill_obj = "statusPillError"
            label    = "Docker unavailable"
        self._set_status_pill(label, "_dynamic", obj_name=pill_obj)

    def _set_status_pill(self, text: str, status_value: str, *,
                         obj_name: str | None = None):
        if obj_name is None:
            # Derive from status_value (which is an InstanceStatus.value)
            obj_name = {
                "generated": "statusPillGenerated",
                "building":  "statusPillBuilding",
                "stopped":   "statusPillStopped",
                "running":   "statusPillRunning",
                "error":     "statusPillError",
            }.get(status_value, "statusPillStopped")
        self._status_pill.setText(f"  {text}  ")
        self._status_pill.setObjectName(obj_name)
        self._status_pill.style().unpolish(self._status_pill)
        self._status_pill.style().polish(self._status_pill)


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

class NetworkingPage(BasePage):
    REFRESH_INTERVAL_MS = 4000

    def __init__(self):
        super().__init__(
            title="Networking",
            subtitle="Per-instance port mappings, container state, and routing."
        )

        self._rows: dict[str, NetworkingRow] = {}

        # Body uses a stack: empty state OR the scrolling list
        self._body_stack = QStackedWidget()
        self._body_stack.addWidget(self._build_empty_state())   # 0
        self._body_stack.addWidget(self._build_list_view())     # 1
        self.add_content(self._body_stack, stretch=1)

        # Wire to the instance store
        store = get_store()
        store.instance_added.connect(lambda _: self._rebuild_all())
        store.instance_removed.connect(lambda _: self._rebuild_all())
        store.instance_updated.connect(self._on_instance_updated)
        store.catalog_reloaded.connect(self._rebuild_all)

        # Periodic Docker-status refresh
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self._refresh_docker_statuses)
        self._refresh_timer.start()

        self._rebuild_all()

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _build_empty_state(self) -> QWidget:
        empty = QWidget()
        layout = QVBoxLayout(empty)
        layout.setContentsMargins(0, 60, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("No instances configured")
        title.setObjectName("emptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("Deploy an instance from the Instances page to see "
                      "its ports and routing here.")
        hint.setObjectName("placeholderText")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)

        layout.addWidget(title)
        layout.addSpacing(6)
        layout.addWidget(hint)
        return empty

    def _build_list_view(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("instanceScroll")
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 8, 0, 8)
        self._list_layout.setSpacing(10)
        self._list_layout.addStretch()  # keep rows top-aligned

        scroll.setWidget(self._list_container)
        return scroll

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _rebuild_all(self):
        # Wipe existing rows
        for row in list(self._rows.values()):
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()

        instances = get_store().all()
        if not instances:
            self._body_stack.setCurrentIndex(0)
            return

        self._body_stack.setCurrentIndex(1)
        for inst in instances:
            row = NetworkingRow(inst)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows[inst.id] = row

        # Kick a status refresh so we don't wait up to 4s for the first paint
        self._refresh_docker_statuses()

    def _on_instance_updated(self, instance: Instance):
        row = self._rows.get(instance.id)
        if row is None:
            self._rebuild_all()
            return
        row._instance = instance
        row.refresh_status_from_instance()

    def _refresh_docker_statuses(self):
        if not self._rows:
            return

        backend = get_backend()
        # Cheap availability check first; if Docker is down, mark everything
        # uniformly and bail.
        if not backend.is_available():
            for row in self._rows.values():
                row.refresh_from_docker_status("unavailable")
            return

        for instance_id, row in list(self._rows.items()):
            inst = get_store().get(instance_id)
            if inst is None:
                continue
            try:
                status = backend.status(inst)
            except (DockerNotAvailable, DockerError):
                status = "unavailable"
            row.refresh_from_docker_status(status)