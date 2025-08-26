# Freebox API Stats Exporter (FASE)

Application **Streamlit** pour explorer, filtrer et exporter la liste des appareils connectés à ta **Freebox OS** — avec tableau, (mini) cartes, stats, **WoL** et **ping**.

---

## ✨ Fonctionnalités

- **Connexion sécurisée** à l’API Freebox OS via `freebox-api` (enregistrement App ID/Device Name à la 1re exécution).
- **Découverte automatique** de la config via `/api_version` : `https_port`, `api_domain`, version d’API, modèle de Freebox.
- **Fallback intelligent** si le domaine principal ne répond pas : essai de `api_domain`, `mafreebox.freebox.fr`, `192.168.1.254`, `freebox.home`, etc. (utile si DNS capricieux).
- **Inventaire détaillé** des appareils (par interfaces LAN / Wi-Fi invité, etc.) incluant :
  - Nom / type (`host_type`), IPv4/IPv6, MAC & fabricant, dernière activité + ancienneté, statut de connectivité.
- **Filtres avancés** : joignables uniquement, interface(s), type(s) d’appareil, recherche plein-texte (nom, IP, MAC, vendor…).
- **Export** des données filtrées en **CSV** et **JSON**.
- **Ping** (optionnel) pour marquer rapidement un appareil **✅/❌/N/A** — repose sur `ping3` si disponible, avec petit cache (TTL 60s) pour éviter le spam ICMP.
- **Wake-on-LAN (WoL)** : envoi d’un paquet WoL vers une MAC (via Freebox ou réseau local, selon ta conf).
- **Robuste aux aléas réseau** : gestion propre des erreurs (ex. `ClientConnectorError`), et des refus d’autorisation (`AuthorizationError`) avec messages clairs à l’écran.
- **(Facultatif)** Aperçu carte si des IP privées sont géolocalisées en interne (à activer selon ton usage).

---

## 📦 Installation

### 1) Cloner

```bash
git clone https://github.com/simongrossi/Freebox-API-Stats-Exporter.git
cd Freebox-API-Stats-Exporter
```

### 2) Dépendances

Installe les libs de `requirements.txt` :

**Linux / macOS**
```bash
python3 -m pip install -r requirements.txt
```

**Windows (PowerShell)**
```powershell
python -m pip install -r requirements.txt
```

> **Optionnel :** si tu veux l’indicateur Ping, installe `ping3` (si elle n’est pas déjà dans `requirements.txt`) :
> ```bash
> pip install ping3
> ```

---

## ▶️ Lancer l’appli

```bash
streamlit run app.py
```

Ouvre ensuite `http://localhost:8501` dans ton navigateur.  
À la **première connexion**, la Freebox affiche une demande d’autorisation : **valide sur l’écran de la box** pour enregistrer l’application.

**Scripts de démarrage rapide :**
- Windows : double-clique `setup.bat`  
- Linux / macOS :
  ```bash
  chmod +x setup.sh
  ./setup.sh
  ```

---

## 🧪 Test rapide (sans UI)

Vérifie l’accès API sans lancer Streamlit :
```bash
python quick_test.py
```

---

## 🛠️ Détails d’identification (par défaut)

- **App ID** : `com.fase.app`  
- **App Name** : `Freebox API Stats Exporter`  
- **App Version** : `1.1`  
- **Device Name** : `FASE-Client-Optimized`  

Tu peux modifier ces valeurs dans le code si besoin.  
⚠️ Si tu changes **App ID** ou **Device Name**, la Freebox considère une **nouvelle appli** → il faudra **ré-autoriser**.

---

## 🧭 Structure du projet

```
Freebox-API-Stats-Exporter/
├── app.py              # Application Streamlit (tableau, filtres, ping/WoL, gestion erreurs)
├── quick_test.py       # Vérification de l’accès API sans UI
├── requirements.txt    # Dépendances Python (streamlit, freebox_api, pandas, etc.)
├── setup.sh            # Lancement Linux/macOS
├── setup.bat           # Lancement Windows
└── README.md           # Ce fichier
```

---

## ❓ FAQ / Dépannage

**L’appli ne se connecte pas, “ClientConnectorError” ?**  
– Vérifie que **Freebox OS** est accessible depuis ton LAN et que HTTPS n’est pas bloqué.  
– L’appli essaie plusieurs hôtes (fallback). Si aucun ne répond, teste depuis un navigateur :  
  - `https://mafreebox.freebox.fr`  
  - `https://192.168.1.254` (ou IP locale de ta box)  
– Assure-toi que l’heure/date de ta machine n’est pas trop décalée (TLS).  

**La Freebox me redemande une autorisation à chaque fois ?**  
– Tu as sans doute modifié **App ID** / **Device Name**. Reviens aux valeurs précédentes, ou ré-autorise avec les nouvelles.  

**Le Ping affiche “N/A” ?**  
– L’IP est vide/indisponible, ou `ping3` n’est pas installée. Installe `ping3` et réessaie.  
– Sur Windows, l’ICMP peut être filtré par le pare-feu.  

**WoL ne réveille pas la machine ?**  
– Vérifie que la carte réseau du PC cible autorise WoL (BIOS/UEFI + OS).  
– Certaines interfaces Wi-Fi ne supportent pas WoL ; privilégie l’Ethernet.  
– Essaye depuis le même VLAN que la machine cible.

---

## 🔒 Permissions & sécurité

- L’app s’enregistre auprès de Freebox OS avec des **identifiants d’application** dédiés.  
- Les données restent **locales** (aucun envoi externe).  
- Tu peux révoquer l’accès dans **Freebox OS → Paramètres → Gestion des accès**.

---

## 📝 Licence

Le dépôt est sous **MIT** (voir `LICENSE`).  
La lib `freebox-api` a sa propre licence ; référez-vous à son dépôt.

---

## 🗺️ Roadmap (idées)

- Historique des connexions par appareil  
- Tags / favoris, et notes par device  
- Export XLSX, et import de listes MAC autorisées  
- Mode “invité” en lecture seule
