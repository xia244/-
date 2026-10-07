"""界面配色与样式表（紫蓝现代风）。"""

PRIMARY = "#6C5CE7"
PRIMARY_DEEP = "#5B4BD6"
ACCENT = "#4F8CFF"
BG = "#F5F6FA"
CARD = "#FFFFFF"
BORDER = "#E6E8F0"
TEXT = "#22242E"
SUBTEXT = "#8A8FA3"
SUCCESS = "#22B07D"
DANGER = "#E5533D"

QSS = f"""
QWidget {{
    font-family: "Microsoft YaHei", "PingFang SC", "WenQuanYi Micro Hei", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QWidget#central {{
    background: {BG};
}}
QFrame#card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QLabel#title {{
    font-size: 20px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#subtitle {{
    font-size: 12px;
    color: {SUBTEXT};
}}
QLabel#section {{
    font-size: 13px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#hint {{
    font-size: 12px;
    color: {SUBTEXT};
}}
QLabel#chip {{
    background: rgba(108, 92, 231, 0.10);
    color: {PRIMARY};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 12px;
}}
QPlainTextEdit, QLineEdit, QComboBox, QSpinBox {{
    background: #FFFFFF;
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 10px;
    selection-background-color: {PRIMARY};
}}
QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {PRIMARY};
}}
QPushButton {{
    border-radius: 10px;
    padding: 9px 18px;
    background: #FFFFFF;
    border: 1px solid {BORDER};
    color: {TEXT};
}}
QPushButton:hover {{
    border-color: {PRIMARY};
    color: {PRIMARY};
}}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PRIMARY}, stop:1 {ACCENT});
    color: #FFFFFF;
    border: none;
    font-size: 14px;
    font-weight: 600;
    padding: 11px 30px;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PRIMARY_DEEP}, stop:1 #3E7BEF);
}}
QPushButton#primary:disabled {{
    background: #C9CCDA;
    color: #FFFFFF;
}}
QPushButton#danger {{
    color: {DANGER};
    border: 1px solid #F3C9C2;
}}
QProgressBar {{
    border: none;
    background: #EDEFF7;
    border-radius: 7px;
    height: 12px;
    text-align: center;
}}
QProgressBar::chunk {{
    border-radius: 7px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PRIMARY}, stop:1 {ACCENT});
}}
QTextEdit#log {{
    background: #FBFCFE;
    border: 1px solid {BORDER};
    border-radius: 12px;
    font-family: Consolas, "Microsoft YaHei", monospace;
    font-size: 12px;
    color: #4A4E63;
}}
QCheckBox {{
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER};
    background: #FFFFFF;
}}
QCheckBox::indicator:checked {{
    background: {PRIMARY};
    border: 1px solid {PRIMARY};
}}
"""
