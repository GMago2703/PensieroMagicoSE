"""Aspetto comune delle finestre: contorni blu un po' più spessi per le schede e i riquadri."""
from __future__ import annotations

BLU = "#1e5bb8"

STILE = f"""
QDialog {{ border: 3px solid {BLU}; }}
QGroupBox {{ border: 2px solid {BLU}; border-radius: 6px; margin-top: 14px; padding-top: 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 4px;
                    color: {BLU}; font-weight: bold; }}
QTableView, QTableWidget, QListView, QListWidget, QTreeView, QPlainTextEdit, QTextEdit, QTextBrowser {{
    border: 2px solid {BLU}; border-radius: 4px; }}
QTabWidget::pane {{ border: 2px solid {BLU}; border-radius: 4px; }}
QTabBar::tab:selected {{ color: {BLU}; font-weight: bold; }}
"""


def applica(app) -> None:
    app.setStyleSheet(STILE)
