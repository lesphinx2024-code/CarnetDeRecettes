# 🍳 Carnet de Recettes

Une application simple en **Python (PyQt6/PySide6)** pour gérer vos recettes de cuisine.

## ✨ Fonctionnalités
- Ajouter / modifier / supprimer une recette
- Ajouter une image
- Mode clair / sombre
- Sauvegarde locale (SQLite)
- Build automatique (AppImage, EXE, DMG) via GitHub Actions

## 🚀 Installation locale
```bash
pip install -r requirements.txt
python recette.py
```

## 🏗️ Build automatique
Une fois le dépôt poussé sur GitHub, le workflow GitHub Actions se charge de :
- Compiler sur **Linux**, **Windows**, et **macOS**
- Produire automatiquement les fichiers `.AppImage`, `.exe` et `.dmg`
- Les rendre disponibles en téléchargement dans la section *Actions → Artifacts*

---
Créé avec ❤️ par David
# CarnetDeRecettes
