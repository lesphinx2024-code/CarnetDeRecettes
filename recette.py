#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application de gestion de recettes - PyQt6
Sauvegarde : SQLite (fichier recettes.db)
Images : copiées dans ./images/
Export PDF via QPrinter / QTextDocument
"""

import sys
import os
import shutil
import sqlite3
from datetime import datetime, timezone


from PyQt6.QtWidgets import (
    QApplication, QWidget, QListWidget, QTextEdit, QLineEdit, QLabel,
    QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QMessageBox, QSpinBox, QGroupBox, QSplitter
)
from PyQt6.QtGui import QPixmap, QAction, QIcon, QGuiApplication, QTextDocument
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtPrintSupport import QPrinter

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "recettes.db")
IMAGES_DIR = os.path.join(APP_DIR, "images")

if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

CATEGORIES = ["Entrée", "Plat", "Dessert", "Boisson", "Autre"]

### Database helpers ###
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS recettes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ingredients TEXT,
            steps TEXT,
            prep_time TEXT,
            category TEXT,
            image_path TEXT,
            created_at TEXT
        );
    """)
    conn.commit()
    conn.close()

def query_all_recipes():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, category FROM recettes ORDER BY name COLLATE NOCASE;")
    rows = c.fetchall()
    conn.close()
    return rows

def get_recipe_by_id(recipe_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, ingredients, steps, prep_time, category, image_path FROM recettes WHERE id = ?;", (recipe_id,))
    row = c.fetchone()
    conn.close()
    return row

def add_recipe_db(name, ingredients, steps, prep_time, category, image_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO recettes (name, ingredients, steps, prep_time, category, image_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?);",
        (name, ingredients, steps, prep_time, category, image_path, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id

def update_recipe_db(recipe_id, name, ingredients, steps, prep_time, category, image_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE recettes SET name=?, ingredients=?, steps=?, prep_time=?, category=?, image_path=? WHERE id=?;",
        (name, ingredients, steps, prep_time, category, image_path, recipe_id)
    )
    conn.commit()
    conn.close()

def delete_recipe_db(recipe_id):
    # returns image path if any so caller can delete file
    row = get_recipe_by_id(recipe_id)
    img = row[6] if row else None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM recettes WHERE id=?;", (recipe_id,))
    conn.commit()
    conn.close()
    return img

def search_recipes_by_text(text, category_filter=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    like = f"%{text}%"
    if category_filter and category_filter != "Tout":
        c.execute(
            "SELECT id, name, category FROM recettes WHERE (name LIKE ? OR ingredients LIKE ? OR steps LIKE ?) AND category = ? ORDER BY name COLLATE NOCASE;",
            (like, like, like, category_filter)
        )
    else:
        c.execute(
            "SELECT id, name, category FROM recettes WHERE name LIKE ? OR ingredients LIKE ? OR steps LIKE ? ORDER BY name COLLATE NOCASE;",
            (like, like, like)
        )
    rows = c.fetchall()
    conn.close()
    return rows

### UI ###
class RecetteApp(QWidget):
    def __init__(self):
        super().__init__()
        init_db()
        self.setWindowTitle("Carnet de recettes")
        self.setMinimumSize(900, 600)
        self.current_recipe_id = None
        self.current_image_path = None
        self.dark_mode = False  # default light

        self._create_actions()
        self._create_ui()
        self.load_recipes()

    def _create_actions(self):
        # toolbar/menu style actions if needed later
        pass

    def _create_ui(self):
        # Left: liste + recherche + filtres
        left_layout = QVBoxLayout()
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher... nom, ingrédient, étape")
        self.search_input.textChanged.connect(self.on_search_changed)
        self.category_filter = QComboBox()
        self.category_filter.addItem("Tout")
        for c in CATEGORIES:
            self.category_filter.addItem(c)
        self.category_filter.currentTextChanged.connect(self.on_search_changed)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.category_filter)

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_recipe_select)

        left_layout.addLayout(search_layout)
        left_layout.addWidget(self.list_widget)

        # Buttons under list
        btns_list_layout = QHBoxLayout()
        self.btn_new = QPushButton("Nouvelle")
        self.btn_new.clicked.connect(self.on_new)
        self.btn_delete = QPushButton("Supprimer")
        self.btn_delete.clicked.connect(self.on_delete)
        self.btn_share = QPushButton("Partager")
        self.btn_share.clicked.connect(self.on_share_menu)
        self.btn_toggle_theme = QPushButton("Activer Sombre")
        self.btn_toggle_theme.clicked.connect(self.toggle_theme)
        btns_list_layout.addWidget(self.btn_new)
        btns_list_layout.addWidget(self.btn_delete)
        btns_list_layout.addWidget(self.btn_share)
        btns_list_layout.addWidget(self.btn_toggle_theme)
        left_layout.addLayout(btns_list_layout)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        # Right: formulaire + image + actions
        right_layout = QVBoxLayout()

        form = QFormLayout()
        self.input_name = QLineEdit()
        self.input_prep_time = QLineEdit()
        self.input_category = QComboBox()
        for c in CATEGORIES:
            self.input_category.addItem(c)

        self.input_ingredients = QTextEdit()
        self.input_steps = QTextEdit()

        form.addRow("Nom :", self.input_name)
        form.addRow("Temps (ex: 20 min) :", self.input_prep_time)
        form.addRow("Catégorie :", self.input_category)
        form.addRow("Ingrédients :", self.input_ingredients)
        form.addRow("Étapes :", self.input_steps)

        # image group
        img_group = QGroupBox("Image du plat")
        img_layout = QVBoxLayout()
        self.img_label = QLabel()
        self.img_label.setFixedSize(QSize(320, 240))
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setStyleSheet("border: 1px solid #ccc;")
        self.btn_load_image = QPushButton("Importer image")
        self.btn_load_image.clicked.connect(self.on_import_image)
        self.btn_remove_image = QPushButton("Supprimer image")
        self.btn_remove_image.clicked.connect(self.on_remove_image)
        img_layout.addWidget(self.img_label)
        img_layout.addWidget(self.btn_load_image)
        img_layout.addWidget(self.btn_remove_image)
        img_group.setLayout(img_layout)

        # action buttons: save / cancel / export pdf / copy
        actions_layout = QHBoxLayout()
        self.btn_save = QPushButton("Enregistrer")
        self.btn_save.clicked.connect(self.on_save)
        self.btn_export_pdf = QPushButton("Exporter PDF")
        self.btn_export_pdf.clicked.connect(self.on_export_pdf)
        self.btn_copy = QPushButton("Copier (presse-papiers)")
        self.btn_copy.clicked.connect(self.on_copy_to_clipboard)
        actions_layout.addWidget(self.btn_save)
        actions_layout.addWidget(self.btn_export_pdf)
        actions_layout.addWidget(self.btn_copy)

        right_layout.addLayout(form)
        right_layout.addWidget(img_group)
        right_layout.addLayout(actions_layout)
        right_layout.addStretch(1)
        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        # Splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # keyboard shortcuts via actions could be added here

    ### Loading / UI update ###
    def load_recipes(self):
        self.list_widget.clear()
        rows = query_all_recipes()
        for r in rows:
            item_text = f"{r[1]}  —  [{r[2]}]"
            # store id in QListWidgetItem data
            item = self.list_widget.addItem(item_text)
        # After filling, we need mapping id-> item; easier to repopulate as pairs
        self.list_widget.clear()
        for r in rows:
            from PyQt6.QtWidgets import QListWidgetItem
            it = QListWidgetItem(f"{r[1]}  —  [{r[2]}]")
            it.setData(Qt.ItemDataRole.UserRole, r[0])
            self.list_widget.addItem(it)
        self.clear_form()

    def clear_form(self):
        self.current_recipe_id = None
        self.current_image_path = None
        self.input_name.clear()
        self.input_prep_time.clear()
        self.input_category.setCurrentIndex(0)
        self.input_ingredients.clear()
        self.input_steps.clear()
        self.img_label.clear()
        self.img_label.setText("Aucune image")
        self.btn_save.setText("Enregistrer")

    def on_recipe_select(self, item):
        recipe_id = item.data(Qt.ItemDataRole.UserRole)
        row = get_recipe_by_id(recipe_id)
        if not row:
            QMessageBox.warning(self, "Erreur", "Recette introuvable.")
            return
        self.current_recipe_id = row[0]
        self.input_name.setText(row[1] or "")
        self.input_ingredients.setPlainText(row[2] or "")
        self.input_steps.setPlainText(row[3] or "")
        self.input_prep_time.setText(row[4] or "")
        if row[5] in CATEGORIES:
            idx = CATEGORIES.index(row[5])
            self.input_category.setCurrentIndex(idx)
        else:
            self.input_category.setCurrentIndex(0)
        self.current_image_path = row[6]
        self._show_image(self.current_image_path)
        self.btn_save.setText("Mettre à jour")

    def _show_image(self, path):
        if path and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                scaled = pix.scaled(self.img_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.img_label.setPixmap(scaled)
                return
        # default
        self.img_label.clear()
        self.img_label.setText("Aucune image")

    ### Search / Filter ###
    def on_search_changed(self, *args):
        text = self.search_input.text().strip()
        category = self.category_filter.currentText()
        rows = search_recipes_by_text(text, category_filter=category if category != "Tout" else None)
        self.list_widget.clear()
        for r in rows:
            from PyQt6.QtWidgets import QListWidgetItem
            it = QListWidgetItem(f"{r[1]}  —  [{r[2]}]")
            it.setData(Qt.ItemDataRole.UserRole, r[0])
            self.list_widget.addItem(it)

    ### Image handling ###
    def on_import_image(self):
        file_filter = "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        fname, _ = QFileDialog.getOpenFileName(self, "Choisir une image", str(APP_DIR), file_filter)
        if not fname:
            return
        try:
            # copy image to images directory with unique name
            ext = os.path.splitext(fname)[1]
            safe_name = f"img_{int(datetime.now(timezone.utc).timestamp() * 1000)}{ext}"
            dest = os.path.join(IMAGES_DIR, safe_name)
            shutil.copy(fname, dest)
            # if editing existing recipe and it had an image, remove old file
            if self.current_image_path and os.path.exists(self.current_image_path):
                try:
                    # only delete if image was in our IMAGES_DIR
                    if os.path.commonpath([os.path.abspath(self.current_image_path), IMAGES_DIR]) == IMAGES_DIR:
                        os.remove(self.current_image_path)
                except Exception:
                    pass
            self.current_image_path = dest
            self._show_image(self.current_image_path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur import image", str(e))

    def on_remove_image(self):
        if not self.current_image_path:
            QMessageBox.information(self, "Image", "Aucune image à supprimer.")
            return
        # delete file if in our images dir
        try:
            if os.path.exists(self.current_image_path) and os.path.commonpath([os.path.abspath(self.current_image_path), IMAGES_DIR]) == IMAGES_DIR:
                os.remove(self.current_image_path)
        except Exception:
            pass
        self.current_image_path = None
        self._show_image(None)

    ### CRUD ###
    def on_new(self):
        self.list_widget.clearSelection()
        self.clear_form()

    def on_save(self):
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Le nom de la recette est obligatoire.")
            return
        ingredients = self.input_ingredients.toPlainText().strip()
        steps = self.input_steps.toPlainText().strip()
        prep_time = self.input_prep_time.text().strip()
        category = self.input_category.currentText()
        image_path = self.current_image_path

        try:
            if self.current_recipe_id:
                update_recipe_db(self.current_recipe_id, name, ingredients, steps, prep_time, category, image_path)
                QMessageBox.information(self, "Sauvegarde", "Recette mise à jour.")
            else:
                new_id = add_recipe_db(name, ingredients, steps, prep_time, category, image_path)
                QMessageBox.information(self, "Sauvegarde", "Recette ajoutée.")
                self.current_recipe_id = new_id
            self.load_recipes()
            # select saved recipe
            self._select_recipe_by_name(name)
        except Exception as e:
            QMessageBox.critical(self, "Erreur sauvegarde", str(e))

    def _select_recipe_by_name(self, name):
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if item.text().startswith(name):
                self.list_widget.setCurrentRow(idx)
                break

    def on_delete(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.information(self, "Supprimer", "Sélectionnez une recette à supprimer.")
            return
        recipe_id = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "Confirmer", "Voulez-vous vraiment supprimer cette recette ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            img = delete_recipe_db(recipe_id)
            # delete image file if inside images dir
            try:
                if img and os.path.exists(img) and os.path.commonpath([os.path.abspath(img), IMAGES_DIR]) == IMAGES_DIR:
                    os.remove(img)
            except Exception:
                pass
            self.load_recipes()

    ### Share / Export ###
    def on_share_menu(self):
        # simple menu: export pdf or copy
        m = QMessageBox(self)
        m.setWindowTitle("Partager")
        m.setText("Choisissez une action pour partager la recette :")
        btn_pdf = m.addButton("Exporter PDF", QMessageBox.ButtonRole.AcceptRole)
        btn_copy = m.addButton("Copier texte", QMessageBox.ButtonRole.AcceptRole)
        btn_cancel = m.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        m.exec()
        chosen = m.clickedButton()
        if chosen == btn_pdf:
            self.on_export_pdf()
        elif chosen == btn_copy:
            self.on_copy_to_clipboard()
        else:
            pass

    def _recipe_to_plaintext(self, recipe):
        # recipe: (id, name, ingredients, steps, prep_time, category, image_path)
        name = recipe[1] or ""
        ingredients = recipe[2] or ""
        steps = recipe[3] or ""
        prep = recipe[4] or ""
        cat = recipe[5] or ""
        out = []
        out.append(f"Recette : {name}")
        out.append(f"Catégorie : {cat}")
        out.append(f"Temps : {prep}")
        out.append("")
        out.append("Ingrédients :")
        out.append(ingredients)
        out.append("")
        out.append("Étapes :")
        out.append(steps)
        return "\n".join(out)

    def on_copy_to_clipboard(self):
        if not self.current_recipe_id:
            QMessageBox.information(self, "Copier", "Sélectionnez une recette d'abord.")
            return
        recipe = get_recipe_by_id(self.current_recipe_id)
        if not recipe:
            QMessageBox.warning(self, "Copier", "Recette introuvable.")
            return
        text = self._recipe_to_plaintext(recipe)
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "Copier", "La recette a été copiée dans le presse-papiers.")

    def on_export_pdf(self):
        if not self.current_recipe_id:
            QMessageBox.information(self, "Exporter", "Sélectionnez une recette d'abord.")
            return
        recipe = get_recipe_by_id(self.current_recipe_id)
        if not recipe:
            QMessageBox.warning(self, "Exporter", "Recette introuvable.")
            return

        # Ask file name
        default_name = f"{recipe[1].strip().replace(' ', '_')}.pdf"
        fname, _ = QFileDialog.getSaveFileName(self, "Exporter en PDF", os.path.join(APP_DIR, default_name), "PDF Files (*.pdf)")
        if not fname:
            return

        # Build HTML to render nicely
        html = f"""
        <html><head><meta charset="utf-8"></head><body>
        <h1>{recipe[1]}</h1>
        <p><b>Catégorie :</b> {recipe[5] or ''} &nbsp;&nbsp; <b>Temps :</b> {recipe[4] or ''}</p>
        <h3>Ingrédients</h3>
        <pre style="font-family: monospace;">{recipe[2] or ''}</pre>
        <h3>Étapes</h3>
        <pre style="font-family: monospace;">{recipe[3] or ''}</pre>
        </body></html>
        """
        doc = QTextDocument()
        doc.setHtml(html)

        printer = QPrinter()
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(fname)
        # Optional: page size, margins can be set
        try:
            doc.print(printer)
            QMessageBox.information(self, "Export PDF", f"Exporté : {fname}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur export", str(e))

    ### Theme ###
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.apply_dark_theme()
            self.btn_toggle_theme.setText("Désactiver Sombre")
        else:
            self.apply_light_theme()
            self.btn_toggle_theme.setText("Activer Sombre")

    def apply_dark_theme(self):
        dark_qss = """
        QWidget { background-color: #222; color: #ddd; }
        QLineEdit, QTextEdit, QComboBox { background-color: #2b2b2b; color: #eee; border: 1px solid #444; }
        QListWidget { background-color: #1e1e1e; color: #ddd; }
        QPushButton { background-color: #333; color: #fff; border: 1px solid #444; padding:6px; }
        QPushButton:hover { background-color: #3c3c3c; }
        QGroupBox { border: 1px solid #444; margin-top: 10px; }
        """
        self.setStyleSheet(dark_qss)

    def apply_light_theme(self):
        self.setStyleSheet("")  # default OS style

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Carnet de recettes")
    # ensure DB
    init_db()
    win = RecetteApp()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
