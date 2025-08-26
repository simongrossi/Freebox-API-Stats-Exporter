
# 📊 Freebox API Stats Exporter (FASE)

Une application **Streamlit** pour explorer, filtrer et exporter la liste des appareils connectés à votre Freebox.

---

## ✨ Fonctionnalités

- 🔐 **Connexion sécurisée** à l’API de Freebox OS via [`freebox-api`](https://github.com/hacf-fr/freebox-api).  
- 🛰️ **Découverte automatique** des paramètres (`https_port`, `api_domain`, version API, modèle) grâce à l’endpoint `/api_version`.  
- 🌐 **Fallback intelligent** : tentative sur différents hôtes (`api_domain`, `mafreebox.freebox.fr`, `192.168.1.254`, `freebox.home`…), utile en cas de DNS ou réseau particulier.  
- 📋 **Liste détaillée des appareils** par interface (LAN, Wi-Fi invité, etc.) avec :  
  - Nom et type (`host_type`)  
  - Adresses IPv4 et IPv6  
  - Adresse MAC et fabricant  
  - Date + ancienneté de la dernière activité  
  - Statut de connectivité (joignable ou non)  
- 🔎 **Filtres avancés** :  
  - Statut (joignables uniquement)  
  - Interfaces réseau  
  - Types d’appareils  
  - Recherche plein texte (nom, IP, MAC, vendor…)  
- 📤 **Export simple** des données filtrées aux formats **CSV** et **JSON**.  

---

## 📦 Installation

### 1. Cloner le dépôt
```bash
git clone https://github.com/your-username/freebox-api-stats-exporter.git
cd freebox-api-stats-exporter
```

### 2. Installer les dépendances
Le script utilise les bibliothèques Python listées dans `requirements.txt`.

- **Linux / macOS** :
```bash
python3 -m pip install -r requirements.txt
```

- **Windows (PowerShell)** :
```powershell
python -m pip install -r requirements.txt
```

---

## ▶️ Lancement

### 🚀 Lancer l'application Streamlit
```bash
streamlit run app.py
```
Puis ouvrez l’adresse [http://localhost:8501](http://localhost:8501) dans votre navigateur.

ℹ️ **Première connexion** : la Freebox affichera une demande d’autorisation sur son écran. Vous devrez la valider pour que l’application puisse accéder à l’API.

---

### ⚡ Scripts de démarrage rapide

- **Windows** : double-cliquez sur `setup.bat`  
- **Linux / macOS** :
```bash
chmod +x setup.sh
./setup.sh
```

---

### 🧪 Test de connexion rapide (optionnel)

Pour vérifier que la connexion à l’API fonctionne **sans lancer l’interface web** :
```bash
python quick_test.py
```

---

## ⚙️ Identité de l'application

Par défaut, l’application s’identifie auprès de la Freebox avec :

- **App ID** : `com.fase.app`  
- **App Name** : `Freebox API Stats Exporter`  
- **App Version** : `1.1`  
- **Device Name** : `FASE-Client-Optimized`  

👉 Vous pouvez modifier ces valeurs dans le code si vous souhaitez personnaliser l’identifiant.

⚠️ **Attention** : si vous changez l’`App ID` ou le `Device Name`, la Freebox considérera qu’il s’agit d’une **nouvelle application** et demandera une nouvelle autorisation.

---

## 📂 Structure du projet

```
freebox-api-stats-exporter/
├── app.py              # Application Streamlit principale
├── quick_test.py       # Script de test pour la connexion à l'API
├── requirements.txt    # Dépendances Python
├── setup.sh            # Script de lancement Linux/macOS
├── setup.bat           # Script de lancement Windows
└── README.md           # Cette documentation
```

---

## 📜 Licence

Ce projet est sous licence **GPLv3**, comme la bibliothèque `freebox-api` dont il dépend.
