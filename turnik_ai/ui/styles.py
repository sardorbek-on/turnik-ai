"""Dark mode: qora + to'q ko'k, ko'k-binafsha gradient aksentlar."""

BG, PANEL, CARD = "#07090f", "#0d1220", "#121a2e"
ACCENT1, ACCENT2 = "#4f7cff", "#8b5cf6"
OK, BAD, WARN, TEXT, MUTED = "#34d399", "#f87171", "#fbbf24", "#e6ebf7", "#7f8bab"
GRAD = f"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {ACCENT1},stop:1 {ACCENT2})"

QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; color: {TEXT}; }}
QMainWindow, QDialog, QWidget#root {{ background: {BG}; }}
QWidget#panel {{ background: {PANEL}; border-radius: 16px; }}
QLabel#video {{ background: #000; border-radius: 16px; border: 1px solid #1d2744; }}
QFrame#card {{ background: {CARD}; border-radius: 14px; border: 1px solid #1d2744; }}
QLabel#cardTitle {{ color: {MUTED}; font-size: 11px; letter-spacing: 1px; }}
QLabel#cardValue {{ font-size: 34px; font-weight: 700; }}
QLabel#state {{ font-size: 20px; font-weight: 700; padding: 8px 14px; border-radius: 12px;
               background: {GRAD}; }}
QLabel#timer {{ font-size: 28px; font-weight: 700; }}
QLabel#errors {{ color: {BAD}; font-size: 13px; }}
QLabel#muted {{ color: {MUTED}; font-size: 12px; }}
QPushButton {{ background: {CARD}; border: 1px solid #25325a; border-radius: 12px; padding: 10px 16px;
              font-weight: 600; }}
QPushButton:hover {{ border-color: {ACCENT1}; }}
QPushButton:disabled {{ color: #4a5473; border-color: #1a2340; }}
QPushButton#start {{ background: {GRAD}; border: none; font-size: 15px; }}
QPushButton#stop {{ background: #3a1620; border: 1px solid #7a2b3b; }}
QComboBox {{ background: {CARD}; border: 1px solid #25325a; border-radius: 10px; padding: 6px 10px; }}
QComboBox QAbstractItemView {{ background: {CARD}; selection-background-color: {ACCENT1}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 10px 18px; color: {MUTED}; font-weight: 600; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT2}; }}
QTableWidget {{ background: {PANEL}; border: none; gridline-color: #1d2744; }}
QHeaderView::section {{ background: {CARD}; color: {MUTED}; border: none; padding: 8px; }}
QProgressBar {{ background: {CARD}; border-radius: 6px; height: 12px; text-align: center; }}
QProgressBar::chunk {{ background: {GRAD}; border-radius: 6px; }}
"""
