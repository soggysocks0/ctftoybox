"""
System Templates page.

Lists the six bundled templates grouped by tier. Clicking 'Generate' on
a row opens the SystemTemplateDialog.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFrame, QPushButton,
    QSizePolicy, QScrollArea,
)

from ui.pages.base_page import BasePage
from ui.widgets.system_template_dialog import SystemTemplateDialog
from system_templates import REGISTRY, SystemTemplate, Tier


_TIER_ORDER = (Tier.EASY, Tier.MEDIUM, Tier.HARD)


# ---------------------------------------------------------------------------
# A single template row
# ---------------------------------------------------------------------------

class SystemTemplateRow(QFrame):
    def __init__(self, template: SystemTemplate, parent_page: "SystemTemplatesPage"):
        super().__init__()
        self.setObjectName("systemTemplateRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._template     = template
        self._parent_page  = parent_page

        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(14)

        # Left: name + summary
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        name_label = QLabel(template.name)
        name_label.setObjectName("systemTemplateName")

        os_badge = QLabel(template.target_os.display_name)
        os_badge.setObjectName("systemTemplateBadge")

        # tier badge: re-color via objectName for high-contrast at-a-glance
        tier_badge = QLabel(template.tier.display_name)
        tier_badge.setObjectName(f"tierBadge_{template.tier.value}")

        title_row.addWidget(name_label)
        title_row.addWidget(os_badge)
        title_row.addWidget(tier_badge)
        title_row.addStretch()

        summary_label = QLabel(template.summary)
        summary_label.setObjectName("systemTemplateSummary")
        summary_label.setWordWrap(True)

        # Vulnerability count line
        vulns_count = len(template.vulnerabilities)
        defs_count  = len(template.defenses)
        meta_text = f"{vulns_count} vulnerabilit{'y' if vulns_count == 1 else 'ies'}"
        if defs_count:
            meta_text += f"  ·  {defs_count} defense{'s' if defs_count != 1 else ''}"
        meta_label = QLabel(meta_text)
        meta_label.setObjectName("placeholderText")

        text_col.addLayout(title_row)
        text_col.addWidget(summary_label)
        text_col.addWidget(meta_label)
        outer.addLayout(text_col, stretch=1)

        # Right: action button
        gen_btn = QPushButton("Generate scripts")
        gen_btn.setObjectName("cardActionPrimary")
        gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gen_btn.clicked.connect(self._on_generate)
        outer.addWidget(gen_btn)

    def _on_generate(self):
        dlg = SystemTemplateDialog(self._template, self._parent_page.window())
        dlg.exec()


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

class SystemTemplatesPage(BasePage):
    def __init__(self):
        super().__init__(
            title="System Templates",
            subtitle=(
                "OS-level setup scripts that turn a real (disposable) host into "
                "a vulnerable lab for pentest practice. Generates scripts only — "
                "no containers or VMs are spun up."
            )
        )

        warning = QLabel(
            "⚠  These scripts deliberately weaken the host they run on. "
            "Run them only on disposable VMs or sandboxed environments — "
            "never on a daily-driver machine."
        )
        warning.setObjectName("calloutWarning")
        warning.setWordWrap(True)
        self.add_content(warning)

        # Scrollable container so the page doesn't blow up if we add more templates
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setObjectName("instanceScroll")

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 4, 0, 4)
        body_layout.setSpacing(14)

        # Group by tier so easy → medium → hard reads visually
        by_tier: dict[Tier, list[SystemTemplate]] = {t: [] for t in _TIER_ORDER}
        for tmpl in REGISTRY:
            by_tier[tmpl.tier].append(tmpl)

        for tier in _TIER_ORDER:
            tier_templates = by_tier.get(tier, [])
            if not tier_templates:
                continue
            section_header = QLabel(f"{tier.display_name} tier")
            section_header.setObjectName("addonsSectionHeader")
            body_layout.addWidget(section_header)

            for tmpl in tier_templates:
                body_layout.addWidget(SystemTemplateRow(tmpl, self))

        body_layout.addStretch()
        scroll.setWidget(body)
        self.add_content(scroll, stretch=1)