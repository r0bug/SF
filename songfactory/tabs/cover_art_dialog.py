"""Cover Art Generation Dialog.

Provides a dialog that uses Claude to generate an optimized image prompt
from song lyrics, then calls the Segmind API to generate cover art
candidates displayed in a 2x2 grid for user selection.
"""

import logging
import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QGridLayout, QMessageBox,
    QProgressBar, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from theme import Theme

logger = logging.getLogger("songfactory.tabs")

_COVER_ART_DIR = os.path.expanduser("~/.songfactory/cover_art")

_ART_PROMPT_SYSTEM = """\
You are an expert visual art director creating prompts for AI image generation.
Given song lyrics and optional style notes, create a vivid, detailed image
generation prompt (~100 words) that captures the mood, themes, and emotion
of the song. Focus on visual imagery, color palettes, composition, lighting,
and artistic style. Do NOT include text, words, or letters in the image.
The image will be used as album cover art — make it striking and iconic.
Output ONLY the image prompt text, nothing else."""


class ClickableImageLabel(QLabel):
    """QLabel that emits clicked signal and shows selection border."""

    clicked = pyqtSignal(int)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self._index = index
        self._selected = False
        self._pixmap_data = None
        self.setFixedSize(300, 300)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def _apply_style(self):
        border_color = Theme.ACCENT if self._selected else Theme.BORDER
        border_width = 3 if self._selected else 1
        self.setStyleSheet(
            f"QLabel {{ background-color: {Theme.PANEL}; "
            f"border: {border_width}px solid {border_color}; "
            f"border-radius: 4px; }}"
        )

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()

    def set_image(self, pixmap: QPixmap, raw_bytes: bytes):
        self._pixmap_data = raw_bytes
        scaled = pixmap.scaled(
            296, 296,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def get_image_bytes(self) -> bytes | None:
        return self._pixmap_data

    def mousePressEvent(self, event):
        self.clicked.emit(self._index)
        super().mousePressEvent(event)


class ArtPromptWorker(QThread):
    """Generate an image prompt from lyrics using Claude."""

    prompt_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, api_key: str, lyrics: str, style_notes: str, model: str):
        super().__init__()
        self._api_key = api_key
        self._lyrics = lyrics
        self._style_notes = style_notes
        self._model = model

    def run(self):
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=self._api_key)
            user_msg = f"Song lyrics:\n{self._lyrics}"
            if self._style_notes:
                user_msg += f"\n\nStyle notes: {self._style_notes}"

            response = client.messages.create(
                model=self._model,
                max_tokens=300,
                system=_ART_PROMPT_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            self.prompt_ready.emit(response.content[0].text.strip())
        except Exception as exc:
            self.error.emit(str(exc))


class ImageGenWorker(QThread):
    """Generate images via Segmind API."""

    image_ready = pyqtSignal(int, bytes)  # index, raw PNG/JPEG bytes
    error = pyqtSignal(str)
    finished_all = pyqtSignal()

    def __init__(self, api_key: str, prompt: str, model: str,
                 width: int, height: int, count: int):
        super().__init__()
        self._api_key = api_key
        self._prompt = prompt
        self._model = model
        self._width = width
        self._height = height
        self._count = count
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        from automation.image_generator import SegmindImageGenerator, ImageGenerationError
        import io

        gen = SegmindImageGenerator(api_key=self._api_key, model=self._model)

        for i in range(self._count):
            if self._stop:
                break
            try:
                results = gen.generate(
                    prompt=self._prompt,
                    width=self._width,
                    height=self._height,
                    count=1,
                )
                raw = results[0]
                logger.info("Image %d/%d received: %d bytes", i + 1, self._count, len(raw))
                # Segmind returns WEBP which Qt may not support;
                # convert everything to PNG via Pillow for safety.
                try:
                    from PIL import Image as PILImage
                    pil_img = PILImage.open(io.BytesIO(raw))
                    buf = io.BytesIO()
                    pil_img.save(buf, format="PNG")
                    raw = buf.getvalue()
                    logger.info("Image %d/%d converted to PNG: %d bytes", i + 1, self._count, len(raw))
                except Exception as conv_exc:
                    logger.warning("Image %d/%d: Pillow conversion failed: %s", i + 1, self._count, conv_exc)
                self.image_ready.emit(i, raw)
            except ImageGenerationError as exc:
                logger.error("Image generation error: %s", exc)
                self.error.emit(str(exc))
                break
            except Exception as exc:
                logger.error("Image %d/%d failed: %s", i + 1, self._count, exc)
                self.error.emit(f"Image {i + 1} failed: {exc}")

        self.finished_all.emit()


class CoverArtDialog(QDialog):
    """Dialog for AI-powered cover art generation."""

    def __init__(self, song_id: int, lyrics: str, title: str, db, parent=None):
        super().__init__(parent)
        self._song_id = song_id
        self._lyrics = lyrics
        self._title = title
        self._db = db
        self._selected_index = -1
        self._image_labels: list[ClickableImageLabel] = []
        self._prompt_worker = None
        self._image_worker = None
        self._result_path = None

        self.setWindowTitle(f"Generate Cover Art — {title}")
        self.setMinimumSize(700, 750)
        self.resize(750, 800)
        self.setStyleSheet(
            f"QDialog {{ background-color: {Theme.BG}; color: {Theme.TEXT}; }}"
        )

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Song lyrics context
        lyrics_label = QLabel("Song Lyrics (context for prompt generation):")
        lyrics_label.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold;")
        layout.addWidget(lyrics_label)

        self.lyrics_edit = QTextEdit()
        self.lyrics_edit.setPlainText(self._lyrics)
        self.lyrics_edit.setMaximumHeight(120)
        layout.addWidget(self.lyrics_edit)

        # Style notes
        style_row = QHBoxLayout()
        style_label = QLabel("Style notes:")
        style_row.addWidget(style_label)
        self.style_edit = QLineEdit()
        self.style_edit.setPlaceholderText(
            "e.g. 'retro vinyl aesthetic', 'dark moody', 'watercolor landscape'..."
        )
        style_row.addWidget(self.style_edit, 1)
        layout.addLayout(style_row)

        # Model + count row
        options_row = QHBoxLayout()

        model_label = QLabel("Model:")
        options_row.addWidget(model_label)
        self.model_combo = QComboBox()
        from automation.image_generator import MODELS
        for display_name, model_id in MODELS.items():
            self.model_combo.addItem(display_name, model_id)
        options_row.addWidget(self.model_combo)

        count_label = QLabel("Images:")
        options_row.addWidget(count_label)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 4)
        self.count_spin.setValue(4)
        options_row.addWidget(self.count_spin)

        options_row.addStretch()

        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setStyleSheet(Theme.accent_button_style())
        self.generate_btn.clicked.connect(self._on_generate)
        options_row.addWidget(self.generate_btn)

        layout.addLayout(options_row)

        # Generated prompt display
        prompt_label = QLabel("Generated image prompt:")
        prompt_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(prompt_label)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(80)
        self.prompt_edit.setPlaceholderText(
            "Click 'Generate' to create an image prompt from the lyrics..."
        )
        layout.addWidget(self.prompt_edit)

        # Regenerate images button (visible after prompt is ready)
        self.regen_btn = QPushButton("Generate Images from Prompt")
        self.regen_btn.setStyleSheet(Theme.secondary_button_style())
        self.regen_btn.clicked.connect(self._on_generate_images)
        self.regen_btn.setVisible(False)
        layout.addWidget(self.regen_btn)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {Theme.DIMMED}; font-style: italic;")
        layout.addWidget(self.status_label)

        # Image grid (2x2)
        grid_label = QLabel("Generated Images (click to select):")
        grid_label.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold;")
        layout.addWidget(grid_label)

        grid = QGridLayout()
        grid.setSpacing(8)
        for i in range(4):
            label = ClickableImageLabel(i)
            label.setText(f"Image {i + 1}")
            label.clicked.connect(self._on_image_clicked)
            self._image_labels.append(label)
            grid.addWidget(label, i // 2, i % 2)
        layout.addLayout(grid)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        self.use_btn = QPushButton("Use Selected")
        self.use_btn.setStyleSheet(Theme.accent_button_style())
        self.use_btn.setEnabled(False)
        self.use_btn.clicked.connect(self._on_use_selected)
        bottom_row.addWidget(self.use_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(Theme.secondary_button_style())
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)

        layout.addLayout(bottom_row)

    def _on_generate(self):
        """Phase 1: Generate art prompt from lyrics via Claude."""
        from secure_config import get_secret
        from ai_models import DEFAULT_MODEL

        api_key = get_secret("api_key", fallback_db=self._db)
        if not api_key:
            QMessageBox.warning(
                self, "No API Key",
                "Anthropic API key is required for prompt generation.\n"
                "Set it in Settings > API Settings."
            )
            return

        lyrics = self.lyrics_edit.toPlainText().strip()
        if not lyrics:
            QMessageBox.warning(self, "No Lyrics", "Please enter song lyrics.")
            return

        model = self._db.get_config("ai_model", "") or DEFAULT_MODEL
        style_notes = self.style_edit.text().strip()

        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Generating image prompt from lyrics...")

        self._prompt_worker = ArtPromptWorker(api_key, lyrics, style_notes, model)
        self._prompt_worker.prompt_ready.connect(self._on_prompt_ready)
        self._prompt_worker.error.connect(self._on_prompt_error)
        self._prompt_worker.start()

    def _on_prompt_ready(self, prompt: str):
        """Prompt generated — show it and start image generation."""
        self.prompt_edit.setPlainText(prompt)
        self.generate_btn.setEnabled(True)
        self.regen_btn.setVisible(True)
        self.status_label.setText("Prompt ready. Generating images...")

        # Auto-start image generation
        self._on_generate_images()

    def _on_prompt_error(self, error: str):
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Error: {error}")
        QMessageBox.critical(self, "Prompt Generation Failed", error)

    def _on_generate_images(self):
        """Phase 2: Generate images from the prompt via Segmind."""
        from secure_config import get_secret

        segmind_key = get_secret("segmind_api_key", fallback_db=self._db)
        if not segmind_key:
            QMessageBox.warning(
                self, "No Segmind Key",
                "Segmind API key is required for image generation.\n"
                "Set it in Settings > API Settings."
            )
            self.progress_bar.setVisible(False)
            self.status_label.setText("")
            return

        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "No Prompt", "Please generate or enter a prompt.")
            return

        model_id = self.model_combo.currentData()
        count = self.count_spin.value()

        # Reset grid
        self._selected_index = -1
        self.use_btn.setEnabled(False)
        for label in self._image_labels:
            label.set_selected(False)
            label.setPixmap(QPixmap())
            label.setText("Generating...")
            label._pixmap_data = None

        # Hide unused slots
        for i in range(4):
            self._image_labels[i].setVisible(i < count)

        self.regen_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Generating {count} image(s)...")

        self._image_worker = ImageGenWorker(
            api_key=segmind_key,
            prompt=prompt,
            model=model_id,
            width=1024,
            height=1024,
            count=count,
        )
        self._image_worker.image_ready.connect(self._on_image_received)
        self._image_worker.error.connect(self._on_image_error)
        self._image_worker.finished_all.connect(self._on_images_done)
        self._image_worker.start()

    def _on_image_received(self, index: int, raw_bytes: bytes):
        if index < len(self._image_labels):
            img = QImage()
            img.loadFromData(raw_bytes)
            if img.isNull():
                logger.warning("Image %d: QImage failed to load %d bytes", index + 1, len(raw_bytes))
                self._image_labels[index].setText("Load failed")
                return
            pixmap = QPixmap.fromImage(img)
            self._image_labels[index].set_image(pixmap, raw_bytes)
            self._image_labels[index].setText("")
            self.status_label.setText(f"Received image {index + 1}...")

    def _on_image_error(self, error: str):
        self.status_label.setText(f"Error: {error}")

    def _on_images_done(self):
        self.progress_bar.setVisible(False)
        self.regen_btn.setEnabled(True)
        self.status_label.setText("Done. Click an image to select it.")

    def _on_image_clicked(self, index: int):
        """Select an image from the grid."""
        if self._image_labels[index].get_image_bytes() is None:
            return

        self._selected_index = index
        for i, label in enumerate(self._image_labels):
            label.set_selected(i == index)
        self.use_btn.setEnabled(True)

    def _on_use_selected(self):
        """Save the selected image and accept the dialog."""
        if self._selected_index < 0:
            return

        raw_bytes = self._image_labels[self._selected_index].get_image_bytes()
        if not raw_bytes:
            return

        os.makedirs(_COVER_ART_DIR, exist_ok=True)
        out_path = os.path.join(_COVER_ART_DIR, f"{self._song_id}.png")

        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(raw_bytes))
            # Resize to exactly 3000x3000 if needed
            if img.size != (3000, 3000):
                img = img.resize((3000, 3000), Image.LANCZOS)
            img.save(out_path, "PNG")
            self._result_path = out_path
            logger.info("Cover art saved: %s (%dx%d)", out_path, 3000, 3000)
            self.accept()
        except ImportError:
            QMessageBox.critical(
                self, "Missing Dependency",
                "Pillow is required to save cover art.\n"
                "Install with: pip install Pillow --break-system-packages"
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Save Failed",
                f"Could not save cover art:\n\n{exc}"
            )

    def get_result_path(self) -> str | None:
        """Return the path to the saved cover art, or None if cancelled."""
        return self._result_path

    def closeEvent(self, event):
        """Stop workers on close."""
        if self._prompt_worker and self._prompt_worker.isRunning():
            self._prompt_worker.wait(2000)
        if self._image_worker and self._image_worker.isRunning():
            self._image_worker.stop()
            self._image_worker.wait(3000)
        super().closeEvent(event)
