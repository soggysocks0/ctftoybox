"""
SystemTemplateDialog — picks live services and an output folder, then
runs the bundle generator and (optionally) opens the result in the file
manager.
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QCheckBox, QFileDialog, QMessageBox, QLineEdit, QScrollArea, QWidget,
)

from system_templates import (
    SystemTemplate, AVAILABLE_SERVICES, generate_template_bundle,
    GenerationError,
)
from instances.store import get_data_root


class SystemTemplateDialog(QDialog):
    """One dialog per template; user picks services + destination."""

    def __init__(self, template: SystemTemplate, parent=None):
        super().__init__(parent)
        self._template = template
        self.setWindowTitle("Generate System Template")
        self.setModal(True)
        self.setMinimumSize(560, 540)

        self._service_checkboxes: dict[str, QCheckBox] = {}

        # Default destination: ~/.ctf_manager/system_templates/<template_id>/
        default_dest = get_data_root() / "system_templates" / template.id
        self._dest_path = str(default_dest)

        self._build_ui()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Header ----
        header = QWidget()
        header.setObjectName("wizardHeader")
        h = QVBoxLayout(header)
        h.setContentsMargins(28, 22, 28, 14)
        h.setSpacing(4)

        title = QLabel("Generate System Template")
        title.setObjectName("wizardTitle")

        subtitle = QLabel(
            f"<b>{self._template.name}</b>  ·  "
            f"{self._template.target_os.display_name}  ·  "
            f"{self._template.tier.display_name}"
        )
        subtitle.setObjectName("wizardStep")
        subtitle.setWordWrap(True)

        h.addWidget(title)
        h.addWidget(subtitle)
        root.addWidget(header)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("wizardDivider")
        root.addWidget(divider)

        # ---- Body (scrollable for small windows) ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(28, 18, 28, 18)
        body_layout.setSpacing(14)

        # Description
        desc = QLabel(self._template.description)
        desc.setObjectName("wizardIntro")
        desc.setWordWrap(True)
        body_layout.addWidget(desc)

        # ---- Vulns list ----
        body_layout.addWidget(self._section_header("Vulnerabilities included"))
        for v in self._template.vulnerabilities:
            body_layout.addWidget(self._make_bullet(v.name, v.detail))
        if not self._template.vulnerabilities:
            note = QLabel("_(none — services you add below will be the only attack surface)_")
            note.setObjectName("wizardHint")
            note.setWordWrap(True)
            body_layout.addWidget(note)

        # ---- Defenses ----
        if self._template.defenses:
            body_layout.addWidget(self._section_header("Defenses enabled"))
            for d in self._template.defenses:
                body_layout.addWidget(self._make_bullet(d.name, d.detail))

        # ---- Services ----
        body_layout.addWidget(self._section_header("Optional live services"))
        services_hint = QLabel(
            "Tick any services to bundle into the setup script. "
            "Each adds its own (deliberate) weaknesses on top of the template."
        )
        services_hint.setObjectName("wizardHint")
        services_hint.setWordWrap(True)
        body_layout.addWidget(services_hint)

        # Show only services compatible with this OS
        for svc in AVAILABLE_SERVICES:
            if self._template.target_os not in svc.supported_os:
                continue
            if svc.id not in self._template.compatible_services:
                continue
            cb = QCheckBox(f"{svc.name}  —  {svc.summary}")
            cb.setObjectName("wizardCheckbox")
            cb.setToolTip(svc.summary)
            self._service_checkboxes[svc.id] = cb
            body_layout.addWidget(cb)

        # ---- Output folder ----
        body_layout.addWidget(self._section_header("Output folder"))
        out_row = QHBoxLayout()
        out_row.setSpacing(8)

        self._dest_input = QLineEdit(self._dest_path)
        self._dest_input.setObjectName("wizardLineEdit")
        self._dest_input.setMinimumHeight(32)
        self._dest_input.textChanged.connect(self._on_dest_changed)

        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("wizardSecondaryBtn")
        browse_btn.clicked.connect(self._on_browse)

        out_row.addWidget(self._dest_input)
        out_row.addWidget(browse_btn)
        body_layout.addLayout(out_row)

        body_layout.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        # ---- Footer ----
        footer = QWidget()
        footer.setObjectName("wizardFooter")
        f = QHBoxLayout(footer)
        f.setContentsMargins(28, 14, 28, 18)
        f.setSpacing(8)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("wizardSecondaryBtn")
        cancel.clicked.connect(self.reject)

        generate = QPushButton("Generate scripts")
        generate.setObjectName("wizardPrimaryBtn")
        generate.setDefault(True)
        generate.clicked.connect(self._on_generate)

        f.addWidget(cancel)
        f.addStretch()
        f.addWidget(generate)
        root.addWidget(footer)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _section_header(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("addonsSectionHeader")
        return lbl

    @staticmethod
    def _make_bullet(name: str, detail: str) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("dialogBullet")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        title = QLabel(f"•  {name}")
        title.setObjectName("dialogBulletTitle")

        body = QLabel(detail)
        body.setObjectName("dialogBulletBody")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)
        return wrap

    def _on_dest_changed(self, text: str):
        self._dest_path = text.strip()

    def _on_browse(self):
        d = QFileDialog.getExistingDirectory(
            self, "Choose output folder", self._dest_path or str(get_data_root()),
        )
        if d:
            self._dest_input.setText(d)

    def _on_generate(self):
        if not self._dest_path:
            QMessageBox.warning(self, "Missing folder", "Please choose an output folder.")
            return

        chosen = [sid for sid, cb in self._service_checkboxes.items() if cb.isChecked()]

        try:
            folder = generate_template_bundle(self._template, chosen, self._dest_path)
        except GenerationError as e:
            QMessageBox.critical(self, "Generation failed", str(e))
            return

        # Offer to open the folder
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Done")
        msg.setText(
            f"Generated <b>{self._template.name}</b> to:<br>"
            f"<code>{folder}</code><br><br>"
            "See README.md for run instructions and "
            "VULNERABILITIES.md for the answer-key inventory."
        )
        open_btn  = msg.addButton("Open folder", QMessageBox.ButtonRole.AcceptRole)
        close_btn = msg.addButton("Close",       QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() is open_btn:
            self._open_folder(str(folder))

        self.accept()

    @staticmethod
    def _open_folder(path: str):
        if QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError:
            pass