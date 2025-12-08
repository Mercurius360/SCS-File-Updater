#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCS File Updater
A professional tool to update the mod_version in SCS/ETS2/ATS mods
Supports .scs, .zip and .rar input → always outputs .scs with version suffix

Author:  Your Name
License: MIT
GitHub:  https://github.com/yourusername/scs-file-updater
"""

import sys
import os
import re
import shutil
import tempfile
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox,
    QProgressBar, QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

try:
    import rarfile
    import patoolib
    HAS_RAR = True
except ImportError:
    HAS_RAR = False

# ----------------------------------------------------------------------
# Worker thread – performs the heavy lifting without freezing the GUI
# ----------------------------------------------------------------------
class UpdateWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)   # success message or new filename
    error = pyqtSignal(str)

    def __init__(self, input_path: Path, new_version: str):
        super().__init__()
        self.input_path = input_path
        self.new_version = new_version.strip()

    def run(self):
        try:
            self.progress.emit("Creating temporary working directory...")
            temp_dir = Path(tempfile.mkdtemp(prefix="scs_updater_"))

            # 1. Extract archive
            self.progress.emit("Extracting archive...")
            if self.input_path.suffix.lower() == ".rar":
                if not HAS_RAR:
                    raise RuntimeError("RAR support not available. Install 'rarfile' and 'patool'.")
                rf = rarfile.RarFile(str(self.input_path))
                rf.extractall(str(temp_dir))
            else:
                # .zip and .scs are identical
                shutil.unpack_archive(str(self.input_path), str(temp_dir), format="zip")

            # 2. Find manifest.sii
            self.progress.emit("Searching for manifest.sii...")
            manifest_path = None
            for root, _, files in os.walk(temp_dir):
                for f in files:
                    if f.lower() == "manifest.sii":
                        manifest_path = Path(root) / f
                        break
                if manifest_path:
                    break

            if not manifest_path:
                raise FileNotFoundError("manifest.sii not found inside the archive.")

            # 3. Update version
            self.progress.emit(f"Updating version to {self.new_version}...")
            manifest_text = manifest_path.read_text(encoding="utf-8", errors="ignore")

            # Regex: mod_version: "anything"
            version_pattern = re.compile(r'(mod_version\s*:\s*")[^"]*(")', re.IGNORECASE)
            if version_pattern.search(manifest_text):
                new_text = version_pattern.sub(rf'\1{self.new_version}\2', manifest_text)
            else:
                # Append if not present
                new_text = manifest_text.rstrip() + f'\nmod_version: "{self.new_version}"\n'

            manifest_path.write_text(new_text, encoding="utf-8")

            # 4. Repackage as .scs
            self.progress.emit("Repackaging as .scs...")
            base_name = self.input_path.stem
            if base_name.lower().endswith(('_v' + self.new_version.replace('.', '_'),)):
                # Avoid double suffix
                output_name = base_name
            else:
                output_name = f"{base_name}_v{self.new_version.replace('.', '_')}"

            output_path = self.input_path.parent / f"{output_name}.scs"

            # Use zip format (SCS is just a ZIP without compression sometimes, but Store works fine)
            shutil.make_archive(
                base_name=str(output_path.with_suffix("")),
                format="zip",
                root_dir=temp_dir
            )
            # Rename .zip → .scs
            temp_zip = output_path.with_suffix(".zip")
            if temp_zip.exists():
                temp_zip.replace(output_path)

            self.progress.emit("Cleaning up temporary files...")
            shutil.rmtree(temp_dir, ignore_errors=True)

            self.finished.emit(str(output_path))

        except Exception as e:
            self.error.emit(str(e))
        finally:
            # Ensure cleanup even on error
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass


# ----------------------------------------------------------------------
# Main GUI Window
# ----------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCS File Updater")
        self.setFixedSize(560, 320)
        self.worker = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Input file
        file_group = QGroupBox("Input File")
        file_layout = QHBoxLayout(file_group)
        self.file_label = QLabel("No file selected")
        self.file_label.setWordWrap(True)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(self.file_label, 1)
        file_layout.addWidget(browse_btn)
        layout.addWidget(file_group)

        # Version input
        version_group = QGroupBox("New Version")
        version_layout = QFormLayout(version_group)
        self.version_edit = QLineEdit()
        self.version_edit.setPlaceholderText("e.g. 5.16.3 or 1.50.2.0 or 5.16.*")
        version_layout.addRow("Version:", self.version_edit)
        layout.addWidget(version_group)

        # Update button
        self.update_btn = QPushButton("Update → New .scs")
        self.update_btn.setFixedHeight(40)
        self.update_btn.clicked.connect(self.start_update)
        layout.addWidget(self.update_btn)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Allow drag & drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        url = event.mimeData().urls()[0]
        path = Path(url.toLocalFile())
        if path.suffix.lower() in {".scs", ".zip", ".rar"}:
            self.set_input_file(path)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select mod archive",
            "", "SCS/ZIP/RAR Files (*.scs *.zip *.rar);;All Files (*.*)"
        )
        if path:
            self.set_input_file(Path(path))

    def set_input_file(self, path: Path):
        self.input_path = path
        self.file_label.setText(str(path))
        self.update_btn.setEnabled(True)

    def start_update(self):
        if not hasattr(self, "input_path"):
            QMessageBox.warning(self, "No file", "Please select an input file first.")
            return

        version = self.version_edit.text().strip()
        if not version:
            QMessageBox.warning(self, "Version missing", "Please enter the new version.")
            return

        # Basic validation
        if not re.match(r"^\d+\.\d+(\.\d+)?(\.\*)?$", version):
            reply = QMessageBox.question(
                self, "Version format",
                f"The version '{version}' does not match the usual pattern (e.g. 5.16.3 or 5.16.*).\n"
                "Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.update_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.status_label.setText("Processing...")

        self.worker = UpdateWorker(self.input_path, version)
        self.worker.progress.connect(self.status_label.setText)
        self.worker.finished.connect(self.on_success)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_success(self, new_file_path: str):
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.status_label.setText("Done!")
        self.update_btn.setEnabled(True)

        QMessageBox.information(
            self,
            "Success",
            f"New file created successfully:\n\n{new_file_path}\n\n"
            "The file is ready to be uploaded or used."
        )

    def on_error(self, msg: str):
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.status_label.setText("Error")
        self.update_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"An error occurred:\n\n{msg}")


# ----------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
