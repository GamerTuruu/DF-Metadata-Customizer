"""Cover art loading and update utilities for the UI."""

import logging
from io import BytesIO
from pathlib import Path

from PIL import Image
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)


class CoverManager:
    """Manage loading and updating cover art for selected songs."""

    def __init__(self, parent):
        self.parent = parent

    def load_cover_image(self, file_data):
        """Load and display cover image."""
        try:
            from mutagen import File as MutagenFile
            from mutagen.id3 import APIC
            import base64

            file_path = file_data.get('path', "")
            if file_path and Path(file_path).exists():
                audio = MutagenFile(file_path)
                if audio is None:
                    self.parent.cover_display.clear()
                    self.parent.cover_display.setText("No cover\nimage")
                    return

                cover_data = None
                file_ext = Path(file_path).suffix.lower()

                # Handle different formats
                if file_ext == '.mp3':
                    # MP3 uses ID3 APIC tags
                    if hasattr(audio, 'tags') and audio.tags:
                        for tag in audio.tags.values():
                            if isinstance(tag, APIC):
                                cover_data = tag.data
                                break
                
                elif file_ext == '.flac':
                    # FLAC stores pictures separately
                    if hasattr(audio, 'pictures') and audio.pictures:
                        cover_data = audio.pictures[0].data
                
                elif file_ext in ('.m4a', '.mp4'):
                    # M4A/MP4 uses 'covr' tag
                    if hasattr(audio, 'tags') and audio.tags and 'covr' in audio.tags:
                        cover_data = bytes(audio.tags['covr'][0])
                
                elif file_ext in ('.ogg', '.opus'):
                    # OGG/Opus uses metadata_block_picture in Vorbis comments
                    if hasattr(audio, 'tags') and audio.tags and 'metadata_block_picture' in audio.tags:
                        try:
                            from mutagen.flac import Picture
                            # Decode base64 and extract picture data
                            picture_data = base64.b64decode(audio.tags['metadata_block_picture'][0])
                            picture = Picture(picture_data)
                            cover_data = picture.data
                        except Exception:
                            pass

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
                from mutagen import File as MutagenFile
                from mutagen.id3 import APIC, ID3

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

                audio = MutagenFile(file_path)
                if audio is None:
                    QMessageBox.warning(self.parent, "Error", "Unsupported file format.")
                    return

                file_ext = Path(file_path).suffix.lower()

                # Handle different formats
                if file_ext == '.mp3':
                    # MP3 uses ID3 tags
                    if audio.tags is None:
                        audio.add_tags()
                    audio.tags.delall('APIC')
                    audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='', data=image_data))
                
                elif file_ext == '.flac':
                    # FLAC uses Vorbis comments and Picture
                    from mutagen.flac import Picture
                    import base64
                    
                    # Clear existing pictures
                    audio.clear_pictures()
                    
                    # Create new picture
                    picture = Picture()
                    picture.type = 3  # Cover (front)
                    picture.mime = 'image/jpeg'
                    picture.desc = ''
                    picture.data = image_data
                    audio.add_picture(picture)
                
                elif file_ext in ('.m4a', '.mp4'):
                    # M4A/MP4 uses MP4 tags
                    from mutagen.mp4 import MP4Cover
                    
                    if audio.tags is None:
                        audio.add_tags()
                    
                    # Determine cover format
                    if image_path.lower().endswith('.png'):
                        cover_format = MP4Cover.FORMAT_PNG
                    else:
                        cover_format = MP4Cover.FORMAT_JPEG
                    
                    audio.tags['covr'] = [MP4Cover(image_data, imageformat=cover_format)]
                
                elif file_ext in ('.ogg', '.opus'):
                    # OGG/Opus uses Vorbis comments with base64 encoded picture
                    from mutagen.flac import Picture
                    import base64
                    
                    picture = Picture()
                    picture.type = 3  # Cover (front)
                    picture.mime = 'image/jpeg'
                    picture.desc = ''
                    picture.data = image_data
                    
                    # Encode picture to base64 and store in metadata_block_picture
                    picture_data = picture.write()
                    encoded_data = base64.b64encode(picture_data).decode('ascii')
                    audio['metadata_block_picture'] = [encoded_data]
                
                else:
                    QMessageBox.warning(self.parent, "Error", f"Cover art not supported for {file_ext} files.")
                    return

                audio.save()

                self.load_cover_image(self.parent.song_files[idx])
                QMessageBox.information(self.parent, "Success", "Cover image updated!")
            except Exception as e:
                QMessageBox.warning(self.parent, "Error", f"Failed to update cover: {e}")
