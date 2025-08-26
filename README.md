# 📊 Freebox API Stats Exporter (Streamlit)

Explorez les appareils connectés à votre Freebox, filtrez, exportez (CSV/JSON) et affichez des statistiques — le tout via Streamlit.

> **FASE** — Freebox API Stats Exporter

## ✨ Fonctionnalités

- Connexion à l’API Freebox OS via [freebox-api](https://github.com/hacf-fr/freebox-api)
- Découverte des **interfaces LAN** (ex. `pub`, `wifiguest`)
- Liste des appareils par interface :
  - Nom, type (`host_type`)
  - IP v4/v6
  - MAC + vendor
  - Dernière activité (date + nombre de jours)
  - Statut `reachable` (joignable ou non)
- Filtres :
  - Joignables uniquement
  - Interfaces spécifiques
  - Types d’hôtes
  - Recherche plein-texte (nom, IP, MAC, vendor…)
- Export CSV et JSON

## 📦 Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/<ton-user>/freebox-api-stats-exporter.git
cd freebox-api-stats-exporter
```

### 2. Installer les dépendances

#### Linux / macOS
```bash
python3 -m pip install -r requirements.txt
```

#### Windows
```powershell
python -m pip install -r requirements.txt
```

## ▶️ Utilisation

### 🔎 Test rapide de connexion

```bash
python quick_test.py
```

- La première fois, la Freebox affichera une **demande d’autorisation** : valide sur l’écran tactile.
- Le token est stocké localement par la librairie et sera réutilisé.
- Exemple de sortie :
  ```
  Interfaces: ['pub', 'wifiguest']
  Hôtes sur pub : 76
  ```

### 🚀 Lancer l’application Streamlit

```bash
python -m streamlit run app.py
```

Ouvre ensuite http://localhost:8501 dans ton navigateur.

### 💻 Windows (setup.bat)

Double-clique sur `setup.bat` pour installer les dépendances et lancer l’app.

### 🐧 Linux/macOS (setup.sh)

```bash
chmod +x setup.sh
./setup.sh
```

---

## ⚙️ Identité de l'application

Par défaut, l’application utilise ces identifiants fixes :

- **App ID** : `com.fase.app`  
- **App Name** : `Freebox API Stats Exporter`  
- **App Version** : `1.0`  
- **Device Name** : `FASE-Client`  

👉 Ces valeurs sont suffisantes pour utiliser l’application.  
Vous pouvez les modifier si vous voulez personnaliser l’identifiant ou différencier vos appareils.  
⚠️ Attention : si vous changez **App ID** ou **Device Name**, la Freebox considérera qu’il s’agit d’une **nouvelle application** et vous devrez valider une nouvelle autorisation sur l’écran.

---

## 📂 Structure du projet

```
freebox-api-stats-exporter/
├── app.py            # appli Streamlit principale
├── quick_test.py     # script test connexion Freebox
├── requirements.txt  # dépendances
├── setup.sh          # script Linux/macOS
├── setup.bat         # script Windows
└── README.md         # ce tutoriel
```

## 📜 Licence

GPLv3 (comme [freebox-api](https://github.com/hacf-fr/freebox-api)).
