import sys, json, os, shutil
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QLineEdit, QLabel,
    QInputDialog, QHeaderView, QComboBox, QMenu
)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPixmap, QAction

class DragDropTableWidget(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.parent_editor = parent
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            # Check if any of the URLs are image files
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg')):
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            # Get the item at the drop position
            item = self.itemAt(event.position().toPoint())
            if item is None:
                event.ignore()
                return
                
            row = item.row()
            col = item.column()
            
            # Check if this is the icon column (assuming it's column 5 based on original code)
            if col == 5:  # Icon column
                for url in event.mimeData().urls():
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg')):
                        try:
                            # Create icons directory if it doesn't exist
                            icons_dir = "./icons"
                            if not os.path.exists(icons_dir):
                                os.makedirs(icons_dir)
                            
                            # Get the file extension
                            _, ext = os.path.splitext(file_path)
                            
                            # Generate a filename based on the item ID or create a unique name
                            item_id_item = self.item(row, 0)  # Assuming column 0 is the ID
                            if item_id_item and item_id_item.text().strip():
                                new_filename = f"{item_id_item.text().strip()}{ext}"
                            else:
                                # Generate unique filename if no ID
                                base_name = os.path.splitext(os.path.basename(file_path))[0]
                                new_filename = f"{base_name}{ext}"
                            
                            destination = os.path.join(icons_dir, new_filename)
                            
                            # Copy the file
                            shutil.copy2(file_path, destination)
                            
                            # Update the table cell with the new filename
                            self.setItem(row, col, QTableWidgetItem(new_filename))
                            
                            if self.parent_editor:
                                self.parent_editor.show_status(f"Image copied to {destination}")
                            
                        except Exception as e:
                            QMessageBox.critical(self, "Error", f"Failed to copy image: {str(e)}")
                        break  # Only handle the first valid image
                
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def show_context_menu(self, position):
        """Show context menu for row operations"""
        item = self.itemAt(position)
        if item is None:
            return
            
        row = item.row()
        
        # Get item ID for display in menu
        id_item = self.item(row, 0)
        item_id = id_item.text() if id_item else f"Row {row + 1}"
        
        menu = QMenu(self)
        
        delete_action = QAction(f"🗑️ Delete Row: {item_id}", self)
        delete_action.triggered.connect(lambda: self.delete_row_with_confirmation(row, item_id))
        menu.addAction(delete_action)
        
        menu.exec(self.mapToGlobal(position))
    
    def delete_row_with_confirmation(self, row, item_id):
        """Delete a row with double confirmation"""
        if self.parent_editor:
            self.parent_editor.delete_row_with_confirmation(row, item_id)

class ItemConfigsEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("itemConfigs Editor - Enhanced")
        self.resize(1200, 700)
        self.file_path = None
        self.data = None
        self.original_data = None  # Store original data for search filtering
        
        self.setup_ui()
        
        # Auto-load itemConfigs.json if it exists in the same folder
        self.auto_load_config()
        
    def setup_ui(self):
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Top buttons layout
        top_layout = QHBoxLayout()
        
        load_btn = QPushButton("📁 Load Different File")
        load_btn.clicked.connect(self.load_json)
        
        reload_btn = QPushButton("🔄 Reload itemConfigs.json")
        reload_btn.clicked.connect(self.reload_config)
        
        save_btn = QPushButton("💾 Save Changes")
        save_btn.clicked.connect(self.save_json)
        
        add_column_btn = QPushButton("➕ Add Column")
        add_column_btn.clicked.connect(self.add_column)
        
        top_layout.addWidget(reload_btn)
        top_layout.addWidget(load_btn)
        top_layout.addWidget(save_btn)
        top_layout.addWidget(add_column_btn)
        top_layout.addStretch()  # Push buttons to the left
        
        # Search layout
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by ID, name, category, or any field...")
        self.search_input.textChanged.connect(self.filter_table)
        
        self.search_column = QComboBox()
        self.search_column.addItem("All Columns")
        self.search_column.currentTextChanged.connect(self.filter_table)
        
        clear_search_btn = QPushButton("Clear")
        clear_search_btn.clicked.connect(self.clear_search)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input, 1)  # Give search input more space
        search_layout.addWidget(QLabel("in:"))
        search_layout.addWidget(self.search_column)
        search_layout.addWidget(clear_search_btn)
        
        # Table
        self.table = DragDropTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "displayName", "category", "rarity", "maxDurability", "icon", "maxStackSize"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        self.table.setSortingEnabled(True)
        
        # Make table headers resizable
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        
        # Status bar
        self.status_label = QLabel("Ready")
        
        # Add all to layout
        layout.addLayout(top_layout)
        layout.addLayout(search_layout)
        layout.addWidget(self.table, 1)  # Give table most of the space
        layout.addWidget(self.status_label)
        
    def show_status(self, message):
        """Show status message"""
        self.status_label.setText(message)
        QApplication.processEvents()  # Update UI immediately
        
    def auto_load_config(self):
        """Automatically load itemConfigs.json from the same folder"""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "itemConfigs.json")
        
        if os.path.exists(config_path):
            try:
                self.load_json_file(config_path)
                self.show_status(f"✅ Auto-loaded itemConfigs.json ({len(self.data)} items)")
            except Exception as e:
                self.show_status(f"❌ Failed to auto-load itemConfigs.json: {str(e)}")
                QMessageBox.warning(
                    self, 
                    "Auto-load Failed", 
                    f"Found itemConfigs.json but failed to load it:\n{str(e)}\n\nPlease use 'Load Different File' to select manually."
                )
        else:
            self.show_status("⚠️ No itemConfigs.json found in current folder - use 'Load Different File' to select one")
    
    def reload_config(self):
        """Reload itemConfigs.json from the same folder"""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "itemConfigs.json")
        
        if os.path.exists(config_path):
            try:
                self.load_json_file(config_path)
                self.show_status(f"🔄 Reloaded itemConfigs.json ({len(self.data)} items)")
                QMessageBox.information(self, "Reload Complete", f"Successfully reloaded itemConfigs.json\n{len(self.data)} items loaded")
            except Exception as e:
                self.show_status(f"❌ Failed to reload itemConfigs.json: {str(e)}")
                QMessageBox.critical(self, "Reload Failed", f"Failed to reload itemConfigs.json:\n{str(e)}")
        else:
            QMessageBox.warning(
                self, 
                "File Not Found", 
                "itemConfigs.json not found in the current folder.\n\nPlease use 'Load Different File' to select a file manually."
            )
    
    def load_json_file(self, file_path):
        """Load JSON file from given path"""
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            
        # Handle different JSON structures
        if "itemConfigs" in raw_data:
            self.data = raw_data["itemConfigs"]
        elif isinstance(raw_data, dict):
            self.data = raw_data
        else:
            raise ValueError("Invalid JSON structure. Expected object with 'itemConfigs' key or direct object.")
            
        self.original_data = self.data.copy()
        self.file_path = file_path
        self.populate_table()
        self.update_search_columns()
        
        # Update window title to show current file
        filename = os.path.basename(file_path)
        self.setWindowTitle(f"itemConfigs Editor - {filename}")
        
    def load_json(self):
        """Load a different JSON file via file dialog"""
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open itemConfigs JSON", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_name:
            try:
                self.load_json_file(file_name)
                self.show_status(f"📁 Loaded {len(self.data)} items from {os.path.basename(file_name)}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error Loading File", f"Failed to load JSON file:\n{str(e)}")
                self.show_status("❌ Failed to load file")

    def update_search_columns(self):
        """Update the search column dropdown with current table headers"""
        self.search_column.clear()
        self.search_column.addItem("All Columns")
        
        for col in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(col)
            if header_item:
                self.search_column.addItem(header_item.text())

    def populate_table(self):
        """Populate the table with data"""
        if not self.data:
            return
            
        self.table.setRowCount(len(self.data))
        
        # Get all possible keys from all items to determine columns needed
        all_keys = set()
        for item in self.data.values():
            if isinstance(item, dict):
                all_keys.update(item.keys())
        
        # Standard columns
        standard_columns = ["displayName", "category", "rarity", "maxDurability", "icon", "maxStackSize"]
        
        # Add any additional columns found in the data
        additional_columns = list(all_keys - set(standard_columns))
        all_columns = standard_columns + additional_columns
        
        # Update table columns if needed
        if self.table.columnCount() != len(all_columns) + 1:  # +1 for ID column
            self.table.setColumnCount(len(all_columns) + 1)
            headers = ["ID"] + all_columns
            self.table.setHorizontalHeaderLabels(headers)
        
        # Populate rows
        for row_idx, (item_id, item) in enumerate(self.data.items()):
            # ID column
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(item_id)))
            
            # Data columns
            for col_idx, key in enumerate(all_columns, 1):
                value = item.get(key, "") if isinstance(item, dict) else ""
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
        
        self.show_status(f"Displaying {len(self.data)} items")

    def filter_table(self):
        """Filter table based on search input"""
        search_text = self.search_input.text().lower()
        search_column = self.search_column.currentText()
        
        if not search_text:
            # Show all rows if search is empty
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            return
        
        # Hide/show rows based on search
        for row in range(self.table.rowCount()):
            should_show = False
            
            if search_column == "All Columns":
                # Search in all columns
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item and search_text in item.text().lower():
                        should_show = True
                        break
            else:
                # Search in specific column
                col_index = self.search_column.currentIndex() - 1  # -1 because "All Columns" is first
                if col_index >= 0 and col_index < self.table.columnCount():
                    item = self.table.item(row, col_index)
                    if item and search_text in item.text().lower():
                        should_show = True
            
            self.table.setRowHidden(row, not should_show)

    def clear_search(self):
        """Clear search input and show all rows"""
        self.search_input.clear()
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, False)

    def add_column(self):
        """Add a new column to the table"""
        column_name, ok = QInputDialog.getText(
            self, "Add Column", "Enter column name:"
        )
        
        if ok and column_name.strip():
            column_name = column_name.strip()
            
            # Add column to table
            current_columns = self.table.columnCount()
            self.table.setColumnCount(current_columns + 1)
            
            # Update headers
            headers = []
            for col in range(current_columns):
                header_item = self.table.horizontalHeaderItem(col)
                headers.append(header_item.text() if header_item else f"Column {col}")
            headers.append(column_name)
            
            self.table.setHorizontalHeaderLabels(headers)
            
            # Add empty cells for existing rows
            for row in range(self.table.rowCount()):
                self.table.setItem(row, current_columns, QTableWidgetItem(""))
            
            # Update search columns
            self.update_search_columns()
            self.show_status(f"Added column: {column_name}")

    def delete_row_with_confirmation(self, row, item_id):
        """Delete a single row with double confirmation"""
        # First confirmation
        reply1 = QMessageBox.question(
            self, 
            "Delete Row - First Confirmation",
            f"Are you sure you want to delete the row for:\n\n'{item_id}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply1 != QMessageBox.StandardButton.Yes:
            return
        
        # Second confirmation
        reply2 = QMessageBox.question(
            self,
            "Delete Row - Final Confirmation",
            f"⚠️ FINAL CONFIRMATION ⚠️\n\nYou are about to permanently delete:\n'{item_id}'\n\nThis action CANNOT be undone!\n\nAre you absolutely sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply2 == QMessageBox.StandardButton.Yes:
            try:
                # Get the item ID before removing the row
                id_item = self.table.item(row, 0)
                deleted_id = id_item.text() if id_item else f"Row {row + 1}"
                
                # Remove the row from table
                self.table.removeRow(row)
                
                # Remove from data dict if it exists
                if self.data and deleted_id in self.data:
                    del self.data[deleted_id]
                
                self.show_status(f"Deleted row: {deleted_id}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete row:\n{str(e)}")
                self.show_status("Delete failed")

    def delete_selected_rows(self):
        """This method is no longer used - kept for compatibility"""
        pass

    def save_json(self):
        """Save the current table data back to JSON"""
        if not self.file_path:
            # If no file path, try to save to itemConfigs.json in current folder
            self.file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "itemConfigs.json")
            reply = QMessageBox.question(
                self,
                "No File Loaded",
                f"No file was loaded. Do you want to save to:\n{self.file_path}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            updated = {}
            
            # Get column headers
            headers = []
            for col in range(1, self.table.columnCount()):  # Skip ID column
                header_item = self.table.horizontalHeaderItem(col)
                headers.append(header_item.text() if header_item else f"column_{col}")
            
            # Process each row
            for row in range(self.table.rowCount()):
                # Skip hidden rows (filtered out)
                if self.table.isRowHidden(row):
                    continue
                    
                id_item = self.table.item(row, 0)
                if not id_item or not id_item.text().strip():
                    continue
                    
                item_id = id_item.text().strip()
                item_data = {}
                
                # Process each data column
                for col_idx, header in enumerate(headers, 1):
                    cell_item = self.table.item(row, col_idx)
                    cell_value = cell_item.text().strip() if cell_item else ""
                    
                    # Try to convert numeric values
                    if header in ["maxDurability", "maxStackSize"]:
                        try:
                            item_data[header] = int(cell_value) if cell_value else 0
                        except ValueError:
                            item_data[header] = cell_value
                    else:
                        item_data[header] = cell_value
                
                updated[item_id] = item_data
            
            # Save to file
            output_data = {"itemConfigs": updated}
            
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            
            # Update data reference
            self.data = updated
            
            QMessageBox.information(self, "Save Successful", f"File saved successfully!\n\nFile: {os.path.basename(self.file_path)}\nSaved {len(updated)} items.")
            self.show_status(f"💾 Saved {len(updated)} items to {os.path.basename(self.file_path)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{str(e)}")
            self.show_status("❌ Save failed")

    def closeEvent(self, event):
        """Handle application closing"""
        # You could add unsaved changes detection here
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("itemConfigs Editor")
    app.setApplicationVersion("2.0")
    
    editor = ItemConfigsEditor()
    editor.show()
    
    sys.exit(app.exec())