"""Cover art loading and update utilities for the UI."""

import logging
from io import BytesIO
from pathlib import Path

from PIL import Image
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class CoverManager:
    """Manage loading and updating cover art for selected songs."""

    def __init__(self, parent):
        self.parent = parent

    def load_cover_image(self, file_data):
        """Load and display cover image."""
        try:
            from mutagen.mp3 import MP3
            from mutagen.id3 import APIC

            file_path = file_data.get('path', "")
            if file_path and Path(file_path).exists():
                audio = MP3(file_path)

                cover_data = None
                if audio.tags:
                    for tag in audio.tags.values():
                        if isinstance(tag, APIC):
                            cover_data = tag.data
                            break

                if cover_data:
                    img = Image.open(BytesIO(cover_data))
                    img.thumbnail((150, 150), Image.Resampling.LANCZOS)

                    img_byte_arr = BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    img_byte_arr.seek(0)

                    pixmap = QPixmap()
                    pixmap.loadFromData(img_byte_arr.read())
                    self.parent.cover_display.setPixmap(pixmap)
                    self.parent.cover_display.setText("")
                else:
                    self.parent.cover_display.clear()
                    self.parent.cover_display.setText("No cover\nimage")
            else:
                self.parent.cover_display.clear()
                self.parent.cover_display.setText("File not\nfound")
        except Exception as e:
            self.parent.cover_display.clear()
            self.parent.cover_display.setText("No cover\nimage")
            logger.debug(f"Error loading cover: {e}")

    def change_cover_image(self):
        """Open file dialog to change cover image."""
        file_dialog = QFileDialog(self.parent)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Image Files (*.jpg *.jpeg *.png *.gif *.bmp)")

        if file_dialog.exec() == QFileDialog.DialogCode.Accepted:
            image_path = file_dialog.selectedFiles()[0]
            try:
                from mutagen.mp3 import MP3
                from mutagen.id3 import APIC

                current_items = self.parent.tree.selectedItems()
                if not current_items:
                    QMessageBox.warning(self.parent, "Warning", "No song selected.")
                    return

                idx = current_items[0].data(0, Qt.ItemDataRole.UserRole)
                if idx is None or idx >= len(self.parent.song_files):
                    return

                file_path = self.parent.song_files[idx].get('path', '')
                if not file_path or not Path(file_path).exists():
                    QMessageBox.warning(self.parent, "Error", "Song file not found.")
                    return

                with open(image_path, 'rb') as img_file:
                    image_data = img_file.read()

                audio = MP3(file_path)
                if audio.tags is None:
                    audio.add_tags()

                audio.tags.delall('APIC')
                audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='', data=image_data))
                audio.save()

                self.load_cover_image(self.parent.song_files[idx])
                QMessageBox.information(self.parent, "Success", "Cover image updated!")
            except Exception as e:
                QMessageBox.warning(self.parent, "Error", f"Failed to update cover: {e}")
