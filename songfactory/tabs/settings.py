"""
Song Factory - Settings Tab

Provides a form-based settings panel grouped into API Settings, Lalals.com
Settings, and General preferences.  All values are persisted to the SQLite
config table via the shared Database instance.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer
import os


# ---------------------------------------------------------------------------
# Colour constants (dark theme)
# ---------------------------------------------------------------------------
_BG = "#2b2b2b"
_PANEL = "#353535"
_TEXT = "#e0e0e0"
_ACCENT = "#E8A838"

_STYLESHEET = f"""
    QWidget {{
        background-color: {_BG};
        color: {_TEXT};
    }}

    QGroupBox {{
        background-color: {_PANEL};
        border: 1px solid #555555;
        border-radius: 6px;
        margin-top: 14px;
        padding: 16px 12px 12px 12px;
        font-weight: bold;
        font-size: 13px;
        color: {_ACCENT};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 2px 10px;
        color: {_ACCENT};
    }}

    QLineEdit, QComboBox, QSpinBox {{
        background-color: {_BG};
        color: {_TEXT};
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 6px 8px;
        font-size: 13px;
        min-height: 24px;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border-color: {_ACCENT};
    }}

    QComboBox::drop-down {{
        border: none;
    }}
    QComboBox QAbstractItemView {{
        background-color: {_PANEL};
        color: {_TEXT};
        selection-background-color: {_ACCENT};
        selection-color: #1e1e1e;
    }}

    QLabel {{
        color: {_TEXT};
        font-size: 13px;
    }}

    QPushButton {{
        background-color: #444444;
        color: {_TEXT};
        border: 1px solid #666666;
        border-radius: 4px;
        padding: 6px 16px;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: #555555;
    }}
    QPushButton:pressed {{
        background-color: #333333;
    }}

    QPushButton#saveButton {{
        background-color: {_ACCENT};
        color: #1a1a1a;
        border: none;
        border-radius: 6px;
        padding: 10px 28px;
        font-weight: bold;
        font-size: 14px;
    }}
    QPushButton#saveButton:hover {{
        background-color: #f0b848;
    }}
    QPushButton#saveButton:pressed {{
        background-color: #d09828;
    }}
"""

# Default download directory
_DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Music", "SongFactory")


class SettingsTab(QWidget):
    """Application settings panel with grouped form fields."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setStyleSheet(_STYLESHEET)
        self._build_ui()
        self.load_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Assemble the full settings layout inside a scroll area."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        root = QVBoxLayout(scroll_content)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ---- API Settings group ----
        api_group = QGroupBox("API Settings")
        api_form = QFormLayout()
        api_form.setSpacing(10)
        api_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Anthropic API Key
        api_key_row = QHBoxLayout()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("sk-ant-...")
        self.api_key_edit.setMinimumWidth(300)
        api_key_row.addWidget(self.api_key_edit, 1)

        self.toggle_key_btn = QPushButton("Show")
        self.toggle_key_btn.setFixedWidth(60)
        self.toggle_key_btn.clicked.connect(self.toggle_api_key_visibility)
        api_key_row.addWidget(self.toggle_key_btn)

        self.test_conn_btn = QPushButton("Test Connection")
        self.test_conn_btn.clicked.connect(self.test_connection)
        api_key_row.addWidget(self.test_conn_btn)

        api_form.addRow("Anthropic API Key:", api_key_row)

        # Default AI Model
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "claude-sonnet-4-20250514",
            "claude-opus-4-0-20250115",
        ])
        api_form.addRow("Default AI Model:", self.model_combo)

        api_group.setLayout(api_form)
        root.addWidget(api_group)

        # ---- Song Submission group ----
        submission_group = QGroupBox("Song Submission")
        submission_form = QFormLayout()
        submission_form.setSpacing(10)
        submission_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Submission mode combo
        self.submission_mode_combo = QComboBox()
        self.submission_mode_combo.addItem("Browser Automation", "browser")
        self.submission_mode_combo.addItem("MusicGPT API (Direct)", "api")
        self.submission_mode_combo.currentIndexChanged.connect(
            self._apply_submission_mode
        )
        submission_form.addRow("Submission Mode:", self.submission_mode_combo)

        # MusicGPT API Key
        musicgpt_key_row = QHBoxLayout()
        self.musicgpt_key_edit = QLineEdit()
        self.musicgpt_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.musicgpt_key_edit.setPlaceholderText("MusicGPT API key...")
        self.musicgpt_key_edit.setMinimumWidth(300)
        musicgpt_key_row.addWidget(self.musicgpt_key_edit, 1)

        self.toggle_musicgpt_key_btn = QPushButton("Show")
        self.toggle_musicgpt_key_btn.setFixedWidth(60)
        self.toggle_musicgpt_key_btn.clicked.connect(
            self._toggle_musicgpt_key_visibility
        )
        musicgpt_key_row.addWidget(self.toggle_musicgpt_key_btn)

        self.test_musicgpt_btn = QPushButton("Test MusicGPT")
        self.test_musicgpt_btn.clicked.connect(self._test_musicgpt_connection)
        musicgpt_key_row.addWidget(self.test_musicgpt_btn)

        submission_form.addRow("MusicGPT API Key:", musicgpt_key_row)

        # Contextual hint label
        self.musicgpt_hint_label = QLabel("")
        self.musicgpt_hint_label.setStyleSheet(
            "color: #888888; font-size: 11px; font-style: italic;"
        )
        self.musicgpt_hint_label.setWordWrap(True)
        submission_form.addRow("", self.musicgpt_hint_label)

        submission_group.setLayout(submission_form)
        root.addWidget(submission_group)

        # ---- Lalals.com Settings group ----
        self.lalals_group = QGroupBox("Lalals.com Settings")
        lalals_form = QFormLayout()
        lalals_form.setSpacing(10)
        lalals_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.lalals_username_edit = QLineEdit()
        self.lalals_username_edit.setPlaceholderText("johnstorlie")
        self.lalals_username_edit.setToolTip(
            "Your lalals.com username (from your profile URL).\n"
            "Used by the Profile Page scraper to discover all songs."
        )
        lalals_form.addRow("Lalals.com Username:", self.lalals_username_edit)

        self.lalals_email_edit = QLineEdit()
        self.lalals_email_edit.setPlaceholderText("your@email.com")
        lalals_form.addRow("Lalals.com Email:", self.lalals_email_edit)

        self.lalals_password_edit = QLineEdit()
        self.lalals_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        lalals_form.addRow("Lalals.com Password:", self.lalals_password_edit)

        browser_row = QHBoxLayout()
        self.browser_path_edit = QLineEdit()
        self.browser_path_edit.setPlaceholderText("/usr/bin/chromium-browser")
        browser_row.addWidget(self.browser_path_edit, 1)

        self.browse_browser_btn = QPushButton("Browse...")
        self.browse_browser_btn.clicked.connect(self.browse_browser_path)
        browser_row.addWidget(self.browse_browser_btn)

        lalals_form.addRow("Browser Path:", browser_row)

        self.lalals_group.setLayout(lalals_form)
        root.addWidget(self.lalals_group)

        # ---- General Settings group ----
        general_group = QGroupBox("General")
        general_form = QFormLayout()
        general_form.setSpacing(10)
        general_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        download_row = QHBoxLayout()
        self.download_dir_edit = QLineEdit()
        self.download_dir_edit.setPlaceholderText(_DEFAULT_DOWNLOAD_DIR)
        download_row.addWidget(self.download_dir_edit, 1)

        self.browse_download_btn = QPushButton("Browse...")
        self.browse_download_btn.clicked.connect(self.browse_download_dir)
        download_row.addWidget(self.browse_download_btn)

        general_form.addRow("Download Directory:", download_row)

        self.max_prompt_spin = QSpinBox()
        self.max_prompt_spin.setRange(100, 500)
        self.max_prompt_spin.setValue(300)
        self.max_prompt_spin.setSuffix(" chars")
        general_form.addRow("Max Prompt Length:", self.max_prompt_spin)

        general_group.setLayout(general_form)
        root.addWidget(general_group)

        # ---- Automation Settings group ----
        self.auto_group = QGroupBox("Automation")
        auto_form = QFormLayout()
        auto_form.setSpacing(10)
        auto_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.xvfb_checkbox = QCheckBox("Run browser in virtual display (Xvfb)")
        self.xvfb_checkbox.setToolTip(
            "Uses Xvfb to run the automation browser invisibly.\n"
            "Requires Xvfb to be installed (sudo apt install xvfb)."
        )
        auto_form.addRow("", self.xvfb_checkbox)

        self.auto_group.setLayout(auto_form)
        root.addWidget(self.auto_group)

        # ---- DistroKid Settings group ----
        dk_group = QGroupBox("DistroKid (Distribution)")
        dk_form = QFormLayout()
        dk_form.setSpacing(10)
        dk_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.dk_email_edit = QLineEdit()
        self.dk_email_edit.setPlaceholderText("your@email.com")
        dk_form.addRow("DistroKid Email:", self.dk_email_edit)

        self.dk_password_edit = QLineEdit()
        self.dk_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.dk_password_edit.setPlaceholderText("DistroKid password")
        dk_form.addRow("DistroKid Password:", self.dk_password_edit)

        self.dk_artist_edit = QLineEdit()
        self.dk_artist_edit.setPlaceholderText("Yakima Finds")
        self.dk_artist_edit.setToolTip(
            "Default artist name for DistroKid uploads.\n"
            "Must match a registered artist on your DistroKid account."
        )
        dk_form.addRow("Default Artist:", self.dk_artist_edit)

        self.dk_songwriter_edit = QLineEdit()
        self.dk_songwriter_edit.setPlaceholderText("Legal name of songwriter")
        self.dk_songwriter_edit.setToolTip(
            "Legal name of the songwriter (required by DistroKid).\n"
            "This is NOT the stage name — use your real legal name."
        )
        dk_form.addRow("Default Songwriter:", self.dk_songwriter_edit)

        dk_hint = QLabel(
            "DistroKid requires email + password + 2FA on first login.\n"
            "The browser session will be saved for future uploads."
        )
        dk_hint.setStyleSheet(
            "color: #888888; font-size: 11px; font-style: italic;"
        )
        dk_hint.setWordWrap(True)
        dk_form.addRow("", dk_hint)

        dk_group.setLayout(dk_form)
        root.addWidget(dk_group)

        # ---- Diagnostics group ----
        self.diag_group = QGroupBox("Diagnostics")
        diag_layout = QHBoxLayout()
        diag_layout.setSpacing(10)

        self.sniffer_btn = QPushButton("Run Network Sniffer (60s)")
        self.sniffer_btn.setToolTip(
            "Opens a browser and logs all network traffic, DOM mutations,\n"
            "and API responses for 60 seconds. Useful for debugging\n"
            "lalals.com automation issues."
        )
        self.sniffer_btn.clicked.connect(self._run_sniffer)
        diag_layout.addWidget(self.sniffer_btn)

        self.open_log_btn = QPushButton("Open Sniffer Log")
        self.open_log_btn.clicked.connect(self._open_sniffer_log)
        diag_layout.addWidget(self.open_log_btn)

        self.open_auto_log_btn = QPushButton("Open Automation Log")
        self.open_auto_log_btn.clicked.connect(self._open_auto_log)
        diag_layout.addWidget(self.open_auto_log_btn)

        diag_layout.addStretch()
        self.diag_group.setLayout(diag_layout)
        root.addWidget(self.diag_group)

        # ---- Backup & Restore group ----
        backup_group = QGroupBox("Backup && Restore")
        backup_layout = QHBoxLayout()
        backup_layout.setSpacing(10)

        self.backup_btn = QPushButton("Backup Now")
        self.backup_btn.setToolTip(
            "Create a timestamped copy of the database\n"
            "in your download directory."
        )
        self.backup_btn.clicked.connect(self._backup_now)
        backup_layout.addWidget(self.backup_btn)

        self.restore_btn = QPushButton("Restore from Backup...")
        self.restore_btn.setToolTip(
            "Replace the current database with a previously\n"
            "saved backup file."
        )
        self.restore_btn.clicked.connect(self._restore_from_backup)
        backup_layout.addWidget(self.restore_btn)

        self.backup_status_label = QLabel("")
        self.backup_status_label.setStyleSheet(
            "color: #888888; font-size: 12px; font-style: italic;"
        )
        backup_layout.addWidget(self.backup_status_label, 1)

        backup_layout.addStretch()
        backup_group.setLayout(backup_layout)
        root.addWidget(backup_group)

        # ---- Bottom: Save button + status label ----
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("saveButton")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self.save_settings)
        bottom_row.addWidget(self.save_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: #4CAF50; font-size: 13px;")
        bottom_row.addWidget(self.status_label)

        bottom_row.addStretch()
        root.addLayout(bottom_row)

        root.addStretch()

        scroll.setWidget(scroll_content)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def load_settings(self):
        """Populate all fields from the database config table."""
        self.api_key_edit.setText(
            self.db.get_config("api_key", "")
        )

        # AI model
        model = self.db.get_config("ai_model", "claude-sonnet-4-20250514")
        idx = self.model_combo.findText(model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        else:
            self.model_combo.setCurrentIndex(0)

        # Lalals.com
        self.lalals_username_edit.setText(
            self.db.get_config("lalals_username", "")
        )
        self.lalals_email_edit.setText(
            self.db.get_config("lalals_email", "")
        )
        self.lalals_password_edit.setText(
            self.db.get_config("lalals_password", "")
        )
        self.browser_path_edit.setText(
            self.db.get_config("browser_path", "")
        )

        # General
        self.download_dir_edit.setText(
            self.db.get_config("download_dir", _DEFAULT_DOWNLOAD_DIR)
        )

        max_prompt = self.db.get_config("max_prompt_length", "300")
        try:
            self.max_prompt_spin.setValue(int(max_prompt))
        except (ValueError, TypeError):
            self.max_prompt_spin.setValue(300)

        # Automation
        self.xvfb_checkbox.setChecked(
            self.db.get_config("use_xvfb", "false").lower() == "true"
        )

        # Song Submission
        self.musicgpt_key_edit.setText(
            self.db.get_config("musicgpt_api_key", "")
        )
        mode = self.db.get_config("submission_mode", "browser")
        idx = self.submission_mode_combo.findData(mode)
        self.submission_mode_combo.setCurrentIndex(max(idx, 0))
        self._apply_submission_mode()

        # DistroKid
        self.dk_email_edit.setText(
            self.db.get_config("dk_email", "")
        )
        self.dk_password_edit.setText(
            self.db.get_config("dk_password", "")
        )
        self.dk_artist_edit.setText(
            self.db.get_config("dk_artist", "Yakima Finds")
        )
        self.dk_songwriter_edit.setText(
            self.db.get_config("dk_songwriter", "")
        )

    def save_settings(self):
        """Persist all field values to the database config table."""
        self.db.set_config("api_key", self.api_key_edit.text().strip())
        self.db.set_config("ai_model", self.model_combo.currentText())
        self.db.set_config("lalals_username", self.lalals_username_edit.text().strip())
        self.db.set_config("lalals_email", self.lalals_email_edit.text().strip())
        self.db.set_config("lalals_password", self.lalals_password_edit.text())
        self.db.set_config("browser_path", self.browser_path_edit.text().strip())

        download_dir = self.download_dir_edit.text().strip()
        if not download_dir:
            download_dir = _DEFAULT_DOWNLOAD_DIR
        self.db.set_config("download_dir", download_dir)

        # Create the download directory if it does not exist
        os.makedirs(download_dir, exist_ok=True)

        self.db.set_config("max_prompt_length", str(self.max_prompt_spin.value()))

        # Automation
        self.db.set_config(
            "use_xvfb", "true" if self.xvfb_checkbox.isChecked() else "false"
        )

        # Song Submission
        self.db.set_config(
            "musicgpt_api_key", self.musicgpt_key_edit.text().strip()
        )
        self.db.set_config(
            "submission_mode", self.submission_mode_combo.currentData()
        )

        # DistroKid
        self.db.set_config("dk_email", self.dk_email_edit.text().strip())
        self.db.set_config("dk_password", self.dk_password_edit.text())
        self.db.set_config(
            "dk_artist", self.dk_artist_edit.text().strip() or "Yakima Finds"
        )
        self.db.set_config("dk_songwriter", self.dk_songwriter_edit.text().strip())

        # Show temporary success message
        self.status_label.setText("Settings saved!")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 13px;")
        QTimer.singleShot(3000, lambda: self.status_label.setText(""))

    # ------------------------------------------------------------------
    # Browse dialogs
    # ------------------------------------------------------------------

    def browse_download_dir(self):
        """Open a folder picker for the download directory."""
        current = self.download_dir_edit.text().strip()
        if not current:
            current = _DEFAULT_DOWNLOAD_DIR

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Download Directory",
            current,
            QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self.download_dir_edit.setText(directory)

    def browse_browser_path(self):
        """Open a file picker for the browser executable."""
        current = self.browser_path_edit.text().strip()
        start_dir = os.path.dirname(current) if current else "/usr/bin"

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Browser Executable",
            start_dir,
            "All Files (*)",
        )
        if file_path:
            self.browser_path_edit.setText(file_path)

    # ------------------------------------------------------------------
    # API key visibility toggle
    # ------------------------------------------------------------------

    def toggle_api_key_visibility(self):
        """Toggle between showing and hiding the API key."""
        if self.api_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_key_btn.setText("Hide")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_key_btn.setText("Show")

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    def test_connection(self):
        """Test the Anthropic API connection with the entered key."""
        api_key = self.api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(
                self,
                "No API Key",
                "Please enter an Anthropic API key before testing the connection.",
            )
            return

        self.test_conn_btn.setEnabled(False)
        self.test_conn_btn.setText("Testing...")

        try:
            from api_client import SongGenerator

            model = self.model_combo.currentText()
            generator = SongGenerator(api_key=api_key, model=model)
            success = generator.test_connection()

            if success:
                QMessageBox.information(
                    self,
                    "Connection Successful",
                    "Successfully connected to the Anthropic API.\n\n"
                    f"Model: {model}",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Connection Failed",
                    "Could not connect to the Anthropic API.\n\n"
                    "Please check your API key and try again.",
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Connection Error",
                f"An error occurred while testing the connection:\n\n{exc}",
            )
        finally:
            self.test_conn_btn.setEnabled(True)
            self.test_conn_btn.setText("Test Connection")

    # ------------------------------------------------------------------
    # Song Submission mode
    # ------------------------------------------------------------------

    def _apply_submission_mode(self):
        """Enable/disable browser-specific widgets based on submission mode."""
        is_api = self.submission_mode_combo.currentData() == "api"

        # Browser-specific widgets: disable in API mode
        browser_widgets = [
            self.lalals_email_edit,
            self.lalals_password_edit,
            self.browser_path_edit,
            self.browse_browser_btn,
            self.xvfb_checkbox,
            self.sniffer_btn,
            self.open_log_btn,
        ]
        for widget in browser_widgets:
            widget.setEnabled(not is_api)

        # Dim the entire groups in API mode
        self.lalals_group.setEnabled(not is_api)
        self.auto_group.setEnabled(not is_api)
        self.diag_group.setEnabled(not is_api)

        if is_api:
            self.musicgpt_hint_label.setText(
                "Direct API mode — songs are submitted, polled, and downloaded "
                "automatically via HTTP. No browser needed."
            )
        else:
            self.musicgpt_hint_label.setText(
                "Optional — used for download fallback when browser automation "
                "is the primary submission mode."
            )

    def _toggle_musicgpt_key_visibility(self):
        """Toggle between showing and hiding the MusicGPT API key."""
        if self.musicgpt_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.musicgpt_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_musicgpt_key_btn.setText("Hide")
        else:
            self.musicgpt_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_musicgpt_key_btn.setText("Show")

    def _test_musicgpt_connection(self):
        """Test the MusicGPT API key by hitting the byId endpoint.

        A 401/403 means invalid key; a 404 (task not found) means valid key.
        """
        api_key = self.musicgpt_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(
                self,
                "No API Key",
                "Please enter a MusicGPT API key before testing.",
            )
            return

        self.test_musicgpt_btn.setEnabled(False)
        self.test_musicgpt_btn.setText("Testing...")

        try:
            import urllib.request
            import urllib.error

            url = (
                "https://api.musicgpt.com/api/public/v1/byId"
                "?conversionType=MUSIC_AI&task_id=test-connection-probe"
            )
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                method="GET",
            )

            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    # 2xx = valid key (unlikely for a fake task_id, but fine)
                    QMessageBox.information(
                        self,
                        "Connection Successful",
                        "MusicGPT API key is valid.",
                    )
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    QMessageBox.critical(
                        self,
                        "Invalid Key",
                        f"MusicGPT API returned HTTP {e.code}.\n\n"
                        "The API key appears to be invalid or expired.",
                    )
                elif e.code == 404:
                    # 404 = task not found but auth accepted
                    QMessageBox.information(
                        self,
                        "Connection Successful",
                        "MusicGPT API key is valid.\n\n"
                        "(Test task not found — this is expected.)",
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Unexpected Response",
                        f"MusicGPT API returned HTTP {e.code}.\n\n"
                        "The key may be valid but the API returned an "
                        "unexpected status.",
                    )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Connection Error",
                f"Error testing MusicGPT connection:\n\n{exc}",
            )
        finally:
            self.test_musicgpt_btn.setEnabled(True)
            self.test_musicgpt_btn.setText("Test MusicGPT")

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def _run_sniffer(self):
        """Launch the network sniffer for 60 seconds."""
        self.sniffer_btn.setEnabled(False)
        self.sniffer_btn.setText("Sniffer running...")
        self.status_label.setText("Network sniffer starting... browser will open.")
        self.status_label.setStyleSheet("color: #2196F3; font-size: 13px;")

        from PyQt6.QtCore import QThread

        class SnifferThread(QThread):
            def run(self_thread):
                try:
                    from automation.network_sniffer import NetworkSniffer
                    sniffer = NetworkSniffer()
                    sniffer.start(duration_s=60)
                except Exception as e:
                    pass  # Logged inside sniffer

        self._sniffer_thread = SnifferThread()
        self._sniffer_thread.finished.connect(self._on_sniffer_done)
        self._sniffer_thread.start()

    def _on_sniffer_done(self):
        """Sniffer thread completed."""
        self.sniffer_btn.setEnabled(True)
        self.sniffer_btn.setText("Run Network Sniffer (60s)")
        log_path = os.path.expanduser("~/.songfactory/network_sniffer.log")
        self.status_label.setText(f"Sniffer complete. Log: {log_path}")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 13px;")
        QTimer.singleShot(5000, lambda: self.status_label.setText(""))

    def _open_sniffer_log(self):
        """Open the sniffer log file with the system default viewer."""
        log_path = os.path.expanduser("~/.songfactory/network_sniffer.log")
        if os.path.exists(log_path):
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(log_path))
        else:
            QMessageBox.information(
                self,
                "No Log File",
                "Sniffer log not found. Run the sniffer first.\n\n"
                f"Expected at: {log_path}",
            )

    def _open_auto_log(self):
        """Open the automation log file."""
        log_path = os.path.expanduser("~/.songfactory/automation.log")
        if os.path.exists(log_path):
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(log_path))
        else:
            QMessageBox.information(
                self,
                "No Log File",
                "Automation log not found.\n\n"
                f"Expected at: {log_path}",
            )

    # ------------------------------------------------------------------
    # Backup & Restore
    # ------------------------------------------------------------------

    def _get_download_dir(self) -> str:
        """Return the configured download directory (or the default)."""
        d = self.download_dir_edit.text().strip()
        return d if d else _DEFAULT_DOWNLOAD_DIR

    def _backup_now(self):
        """Create a database backup in the download directory."""
        download_dir = self._get_download_dir()
        try:
            path = self.db.backup_to(download_dir)
            filename = os.path.basename(path)
            self.backup_status_label.setText(f"Last backup: {filename}")
            self.backup_status_label.setStyleSheet(
                "color: #4CAF50; font-size: 12px; font-style: italic;"
            )
            QMessageBox.information(
                self,
                "Backup Created",
                f"Database backed up successfully.\n\n{path}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Backup Failed",
                f"Could not create backup:\n\n{exc}",
            )

    def _restore_from_backup(self):
        """Let the user pick a backup and restore it."""
        from database import Database

        download_dir = self._get_download_dir()
        backups = Database.detect_backups(download_dir)

        selected_path = None

        if backups:
            # Build choice list: "2026-02-08 14:30:22  (1.2 MB)"
            items = []
            for b in backups:
                size_mb = b["size"] / (1024 * 1024)
                items.append(f"{b['date']}  ({size_mb:.1f} MB)  —  {b['filename']}")

            choice, ok = QInputDialog.getItem(
                self,
                "Restore from Backup",
                "Select a backup to restore (newest first):",
                items,
                0,
                False,
            )
            if ok and choice:
                idx = items.index(choice)
                selected_path = backups[idx]["path"]
            elif ok:
                return  # cancelled
            else:
                # User cancelled — offer to browse manually
                selected_path = self._browse_for_backup()
        else:
            # No backups found — offer to browse
            answer = QMessageBox.question(
                self,
                "No Backups Found",
                f"No backup files found in:\n{download_dir}\n\n"
                "Would you like to browse for a backup file?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                selected_path = self._browse_for_backup()

        if not selected_path:
            return

        # Confirm before restoring
        confirm = QMessageBox.warning(
            self,
            "Confirm Restore",
            "This will replace your current database with the selected backup.\n\n"
            "A safety copy of the current database will be saved in\n"
            "~/.songfactory/songfactory_pre_restore.db\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self.db.restore_from(selected_path)
            self.backup_status_label.setText("Database restored — restart recommended")
            self.backup_status_label.setStyleSheet(
                "color: #2196F3; font-size: 12px; font-style: italic;"
            )
            QMessageBox.information(
                self,
                "Restore Complete",
                "Database restored successfully.\n\n"
                "Please restart Song Factory for all changes to take effect.",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Restore Failed",
                f"Could not restore database:\n\n{exc}",
            )

    def _browse_for_backup(self) -> str | None:
        """Open a file dialog to pick a .db backup file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Backup File",
            self._get_download_dir(),
            "SQLite Database (*.db);;All Files (*)",
        )
        return path if path else None
