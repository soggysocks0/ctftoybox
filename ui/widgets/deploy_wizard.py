"""
Deploy wizard.

A modal QDialog with four pages:

  1. Name        — what should this instance be called?
  2. Resources   — CPU, memory, port mapping (with a sensible baseline)
  3. Template    — pick a Vulnerability template from the chosen category
  4. Review      — confirm, then "Generate" creates the working dir and
                   adds an Instance to the store

The wizard takes a starting Category (selected from the Deploy menu).
On success it adds the new Instance to the global store and closes.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QWidget, QDoubleSpinBox, QSpinBox,
    QListWidget, QListWidgetItem, QMessageBox, QFrame, QFormLayout,
    QGridLayout,
)

from vulnerabilities import (
    Category, Vulnerability, get_vulnerabilities, get_vulnerability,
)
from instances import (
    Instance, InstanceStatus, ResourceSpec,
    get_store, InstanceStore,
)
from instances.store import make_instance_id
from generators import generate_for_instance, GenerationError


# ---------------------------------------------------------------------------
# Resource baselines per category — sensible starting points.
# ---------------------------------------------------------------------------

_BASELINES: dict[Category, ResourceSpec] = {
    Category.REVERSE_ENGINEERING: ResourceSpec(cpu_cores=0.5, memory_mb=256, port_mappings=[]),
    Category.BINARY_EXPLOITATION: ResourceSpec(cpu_cores=1.0, memory_mb=512, port_mappings=[(31337, 31337)]),
    Category.WEB_EXPLOITATION:    ResourceSpec(cpu_cores=1.0, memory_mb=512, port_mappings=[(8080,  8080)]),
    Category.FORENSICS:           ResourceSpec(cpu_cores=0.5, memory_mb=256, port_mappings=[]),
    Category.CUSTOM:              ResourceSpec(cpu_cores=1.0, memory_mb=512, port_mappings=[]),
}


# ---------------------------------------------------------------------------
# The wizard
# ---------------------------------------------------------------------------

class DeployWizard(QDialog):
    """Modal wizard for creating a new instance."""

    instance_created = pyqtSignal(object)  # emits the new Instance

    STEPS = ("Name", "Resources", "Template", "Review")

    def __init__(self, category: Category, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deploy New Instance")
        self.setModal(True)
        self.setMinimumSize(620, 480)

        self._category = category
        self._templates = get_vulnerabilities(category)

        # In-progress instance config
        self._instance_name = ""
        self._resources     = _BASELINES.get(category, ResourceSpec()).__class__(
            cpu_cores=_BASELINES[category].cpu_cores,
            memory_mb=_BASELINES[category].memory_mb,
            port_mappings=list(_BASELINES[category].port_mappings),
        )
        self._selected_template_id: str | None = (
            self._templates[0].id if self._templates else None
        )

        self._build_ui()
        self._update_step(0)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Header ---
        header = QWidget()
        header.setObjectName("wizardHeader")
        h = QVBoxLayout(header)
        h.setContentsMargins(28, 22, 28, 14)
        h.setSpacing(4)

        self._title_label = QLabel("Deploy New Instance")
        self._title_label.setObjectName("wizardTitle")

        self._step_label = QLabel("Step 1 of 4 · Name")
        self._step_label.setObjectName("wizardStep")

        h.addWidget(self._title_label)
        h.addWidget(self._step_label)

        # Step indicator dots
        dots_row = QHBoxLayout()
        dots_row.setSpacing(6)
        dots_row.setContentsMargins(0, 8, 0, 0)
        self._dots: list[QLabel] = []
        for i, _ in enumerate(self.STEPS):
            dot = QLabel("●")
            dot.setObjectName("wizardDot")
            self._dots.append(dot)
            dots_row.addWidget(dot)
        dots_row.addStretch()
        h.addLayout(dots_row)

        root.addWidget(header)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("wizardDivider")
        root.addWidget(divider)

        # --- Page stack ---
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_name_page())
        self._stack.addWidget(self._build_resources_page())
        self._stack.addWidget(self._build_template_page())
        self._stack.addWidget(self._build_review_page())
        root.addWidget(self._stack, stretch=1)

        # --- Footer with buttons ---
        footer = QWidget()
        footer.setObjectName("wizardFooter")
        f = QHBoxLayout(footer)
        f.setContentsMargins(28, 14, 28, 18)
        f.setSpacing(8)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("wizardSecondaryBtn")
        self._cancel_btn.clicked.connect(self.reject)

        self._back_btn = QPushButton("Back")
        self._back_btn.setObjectName("wizardSecondaryBtn")
        self._back_btn.clicked.connect(self._go_back)

        self._next_btn = QPushButton("Next")
        self._next_btn.setObjectName("wizardPrimaryBtn")
        self._next_btn.setDefault(True)
        self._next_btn.clicked.connect(self._go_next)

        f.addWidget(self._cancel_btn)
        f.addStretch()
        f.addWidget(self._back_btn)
        f.addWidget(self._next_btn)

        root.addWidget(footer)

    # --- Page 1: Name ---
    def _build_name_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(10)

        intro = QLabel(
            f"You're deploying a <b>{self._category.display_name}</b> challenge. "
            "Give this instance a memorable name — you'll use it to identify "
            "it in the instance list."
        )
        intro.setWordWrap(True)
        intro.setObjectName("wizardIntro")
        layout.addWidget(intro)

        layout.addSpacing(6)

        name_label = QLabel("Instance name")
        name_label.setObjectName("wizardFieldLabel")
        layout.addWidget(name_label)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. midnight-crackme")
        self._name_input.setObjectName("wizardLineEdit")
        self._name_input.setMinimumHeight(34)
        self._name_input.textChanged.connect(self._on_name_changed)
        layout.addWidget(self._name_input)

        hint = QLabel("Letters, numbers, dashes, underscores. 1–48 characters.")
        hint.setObjectName("wizardHint")
        layout.addWidget(hint)

        layout.addStretch()
        return page

    # --- Page 2: Resources ---
    def _build_resources_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(10)

        baseline = _BASELINES[self._category]
        port_text = (
            ", ".join(f"{h}→{c}" for h, c in baseline.port_mappings)
            if baseline.port_mappings else "no service ports"
        )

        intro = QLabel(
            f"Allocate resources for this instance. The recommended baseline for "
            f"<b>{self._category.display_name}</b> is "
            f"<b>{baseline.cpu_cores}</b> CPU, <b>{baseline.memory_mb} MB</b> RAM, "
            f"with {port_text}. Adjust to fit your host."
        )
        intro.setWordWrap(True)
        intro.setObjectName("wizardIntro")
        layout.addWidget(intro)

        layout.addSpacing(6)

        # Form
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._cpu_input = QDoubleSpinBox()
        self._cpu_input.setRange(0.1, 16.0)
        self._cpu_input.setSingleStep(0.1)
        self._cpu_input.setDecimals(1)
        self._cpu_input.setSuffix(" cores")
        self._cpu_input.setValue(self._resources.cpu_cores)
        self._cpu_input.setObjectName("wizardSpinBox")
        self._cpu_input.setMinimumHeight(32)
        self._cpu_input.valueChanged.connect(
            lambda v: setattr(self._resources, "cpu_cores", float(v))
        )

        self._mem_input = QSpinBox()
        self._mem_input.setRange(64, 16384)
        self._mem_input.setSingleStep(64)
        self._mem_input.setSuffix(" MB")
        self._mem_input.setValue(self._resources.memory_mb)
        self._mem_input.setObjectName("wizardSpinBox")
        self._mem_input.setMinimumHeight(32)
        self._mem_input.valueChanged.connect(
            lambda v: setattr(self._resources, "memory_mb", int(v))
        )

        form.addRow(self._field_label("CPU"),    self._cpu_input)
        form.addRow(self._field_label("Memory"), self._mem_input)

        # Port mapping (one row only for now; baseline either has 0 or 1)
        if baseline.port_mappings:
            host0, container0 = baseline.port_mappings[0]
            self._has_port_mapping = True

            port_row = QHBoxLayout()
            port_row.setSpacing(8)

            self._host_port_input = QSpinBox()
            self._host_port_input.setRange(1, 65535)
            self._host_port_input.setValue(host0)
            self._host_port_input.setObjectName("wizardSpinBox")
            self._host_port_input.setMinimumHeight(32)

            arrow = QLabel("→")
            arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
            arrow.setFixedWidth(20)

            self._container_port_input = QSpinBox()
            self._container_port_input.setRange(1, 65535)
            self._container_port_input.setValue(container0)
            self._container_port_input.setObjectName("wizardSpinBox")
            self._container_port_input.setMinimumHeight(32)
            self._container_port_input.setEnabled(False)  # template decides this

            port_row.addWidget(self._host_port_input)
            port_row.addWidget(arrow)
            port_row.addWidget(self._container_port_input)
            port_row.addStretch()

            self._host_port_input.valueChanged.connect(self._sync_port_mapping)
            self._container_port_input.valueChanged.connect(self._sync_port_mapping)

            form.addRow(self._field_label("Port (host → container)"), port_row)
        else:
            self._has_port_mapping = False
            no_ports = QLabel("This challenge type doesn't expose a network service.")
            no_ports.setObjectName("wizardHint")
            form.addRow(self._field_label("Ports"), no_ports)

        layout.addLayout(form)
        layout.addStretch()
        return page

    def _sync_port_mapping(self):
        if not getattr(self, "_has_port_mapping", False):
            return
        self._resources.port_mappings = [
            (self._host_port_input.value(), self._container_port_input.value())
        ]

    # --- Page 3: Template ---
    def _build_template_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(10)

        intro = QLabel(
            "Choose a template to base this instance on. "
            "Each template generates a working Dockerfile and any source code needed."
        )
        intro.setWordWrap(True)
        intro.setObjectName("wizardIntro")
        layout.addWidget(intro)

        # Template list — left column shows names, right column shows details.
        body = QHBoxLayout()
        body.setSpacing(16)

        self._template_list = QListWidget()
        self._template_list.setObjectName("wizardList")
        self._template_list.setMinimumWidth(220)
        for tmpl in self._templates:
            item = QListWidgetItem(tmpl.name)
            item.setData(Qt.ItemDataRole.UserRole, tmpl.id)
            self._template_list.addItem(item)
        if self._templates:
            self._template_list.setCurrentRow(0)
        self._template_list.currentItemChanged.connect(self._on_template_selected)
        body.addWidget(self._template_list, stretch=1)

        # Detail panel
        self._detail_panel = QWidget()
        self._detail_panel.setObjectName("wizardDetailPanel")
        dp = QVBoxLayout(self._detail_panel)
        dp.setContentsMargins(14, 12, 14, 12)
        dp.setSpacing(6)

        self._detail_name = QLabel()
        self._detail_name.setObjectName("wizardDetailName")
        self._detail_name.setWordWrap(True)

        self._detail_desc = QLabel()
        self._detail_desc.setObjectName("wizardDetailDesc")
        self._detail_desc.setWordWrap(True)

        self._detail_meta = QLabel()
        self._detail_meta.setObjectName("wizardDetailMeta")
        self._detail_meta.setWordWrap(True)

        dp.addWidget(self._detail_name)
        dp.addWidget(self._detail_desc)
        dp.addSpacing(6)
        dp.addWidget(self._detail_meta)
        dp.addStretch()

        body.addWidget(self._detail_panel, stretch=2)
        layout.addLayout(body, stretch=1)

        # Trigger initial detail refresh
        if self._templates:
            self._refresh_detail(self._templates[0])

        return page

    def _on_template_selected(self, current: QListWidgetItem | None, _prev):
        if current is None:
            return
        tmpl_id = current.data(Qt.ItemDataRole.UserRole)
        self._selected_template_id = tmpl_id
        tmpl = get_vulnerability(tmpl_id)
        if tmpl is not None:
            self._refresh_detail(tmpl)

    def _refresh_detail(self, tmpl: Vulnerability):
        self._detail_name.setText(f"<b>{tmpl.name}</b>")
        self._detail_desc.setText(tmpl.short_desc)
        meta_lines = [
            f"<b>Difficulty:</b> {tmpl.difficulty.value}",
            f"<b>What you'll learn:</b> {tmpl.learning_goal}",
        ]
        if tmpl.tags:
            meta_lines.append(f"<b>Tags:</b> {', '.join(tmpl.tags)}")
        self._detail_meta.setText("<br>".join(meta_lines))

    # --- Page 4: Review ---
    def _build_review_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(10)

        intro = QLabel(
            "Review your configuration. Pressing <b>Generate</b> will create the "
            "instance folder and write all the Dockerfile and helper scripts."
        )
        intro.setWordWrap(True)
        intro.setObjectName("wizardIntro")
        layout.addWidget(intro)

        # Two-column summary
        self._summary_grid = QGridLayout()
        self._summary_grid.setHorizontalSpacing(20)
        self._summary_grid.setVerticalSpacing(8)
        layout.addLayout(self._summary_grid)

        layout.addStretch()
        return page

    def _refresh_review(self):
        # Wipe and rebuild
        while self._summary_grid.count():
            item = self._summary_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        tmpl = get_vulnerability(self._selected_template_id) if self._selected_template_id else None
        if self._resources.port_mappings:
            ports_str = ", ".join(f"{h} → {c}" for h, c in self._resources.port_mappings)
        else:
            ports_str = "(none)"

        rows = [
            ("Name",     self._instance_name or "(unset)"),
            ("Category", self._category.display_name),
            ("Template", tmpl.name if tmpl else "(none)"),
            ("CPU",      f"{self._resources.cpu_cores} cores"),
            ("Memory",   f"{self._resources.memory_mb} MB"),
            ("Ports",    ports_str),
        ]
        for r, (k, v) in enumerate(rows):
            klabel = QLabel(k)
            klabel.setObjectName("wizardReviewKey")
            vlabel = QLabel(v)
            vlabel.setObjectName("wizardReviewValue")
            vlabel.setWordWrap(True)
            self._summary_grid.addWidget(klabel, r, 0, Qt.AlignmentFlag.AlignTop)
            self._summary_grid.addWidget(vlabel, r, 1, Qt.AlignmentFlag.AlignTop)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("wizardFieldLabel")
        return lbl

    def _on_name_changed(self, text: str):
        self._instance_name = text.strip()

    @staticmethod
    def _slugify(name: str) -> str:
        out = []
        for ch in name.lower():
            if ch.isalnum() or ch in "-_":
                out.append(ch)
            elif ch == " ":
                out.append("-")
        return "".join(out).strip("-_") or "instance"

    def _validate_current_step(self) -> tuple[bool, str]:
        idx = self._stack.currentIndex()
        if idx == 0:
            n = self._instance_name
            if not n:
                return False, "Please enter an instance name."
            if len(n) > 48:
                return False, "Name is too long (max 48 characters)."
            for ch in n:
                if not (ch.isalnum() or ch in "-_ "):
                    return False, "Name may only contain letters, numbers, spaces, dashes, and underscores."
        elif idx == 2:
            if not self._selected_template_id:
                return False, "Please select a template."
        return True, ""

    # ------------------------------------------------------------------
    # Step navigation
    # ------------------------------------------------------------------

    def _update_step(self, idx: int):
        idx = max(0, min(idx, self._stack.count() - 1))
        self._stack.setCurrentIndex(idx)
        self._step_label.setText(f"Step {idx + 1} of {len(self.STEPS)} · {self.STEPS[idx]}")

        # Highlight current dot
        for i, dot in enumerate(self._dots):
            if i < idx:
                dot.setProperty("state", "done")
            elif i == idx:
                dot.setProperty("state", "current")
            else:
                dot.setProperty("state", "pending")
            # Re-polish so QSS rule for [state="..."] applies
            dot.style().unpolish(dot)
            dot.style().polish(dot)

        self._back_btn.setEnabled(idx > 0)
        last_step = idx == self._stack.count() - 1
        self._next_btn.setText("Generate" if last_step else "Next")

        if last_step:
            self._refresh_review()

    def _go_back(self):
        self._update_step(self._stack.currentIndex() - 1)

    def _go_next(self):
        ok, msg = self._validate_current_step()
        if not ok:
            QMessageBox.warning(self, "Hold on", msg)
            return

        if self._stack.currentIndex() < self._stack.count() - 1:
            self._update_step(self._stack.currentIndex() + 1)
        else:
            self._do_generate()

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    def _do_generate(self):
        tmpl = get_vulnerability(self._selected_template_id or "")
        if tmpl is None:
            QMessageBox.critical(self, "Error", "Selected template no longer exists.")
            return

        # Build instance + working dir
        slug = self._slugify(self._instance_name)
        inst_id = make_instance_id(slug)
        wd = InstanceStore.working_dir_for(inst_id)

        instance = Instance(
            id=inst_id,
            name=self._instance_name,
            template_id=tmpl.id,
            category=tmpl.category.value,
            resources=ResourceSpec(
                cpu_cores=self._resources.cpu_cores,
                memory_mb=self._resources.memory_mb,
                port_mappings=list(self._resources.port_mappings),
            ),
            working_dir=str(wd),
            status=InstanceStatus.GENERATED,
        )

        try:
            generate_for_instance(instance, tmpl)
        except GenerationError as e:
            QMessageBox.critical(self, "Generation failed", str(e))
            return

        # Persist + notify
        get_store().add(instance)

        # Seed the audit log with the creation event
        from runtime.audit import get_audit_log, AuditKind
        get_audit_log().record(
            instance.working_dir,
            AuditKind.CREATED,
            f"Instance created from template '{tmpl.name}' "
            f"(category={tmpl.category.display_name})",
        )

        self.instance_created.emit(instance)
        self.accept()