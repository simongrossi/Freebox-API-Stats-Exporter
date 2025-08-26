# app.py (Freebox API Stats Exporter - v5.1 : Correction du CacheReplayClosureError)
import asyncio
import platform
import subprocess
import json
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import pandas as pd
import streamlit as st

from freebox_api import Freepybox
from freebox_api.exceptions import AuthorizationError
from aiohttp import ClientConnectorError

# --- Configuration de la page ---
st.set_page_config(page_title="Freebox API Stats Exporter", page_icon="📊", layout="wide")
st.title("📊 Freebox API Stats Exporter")
st.caption("Explorer, filtrer et exporter les appareils Freebox — tableau, cartes, stats, WoL et ping.")

# --- Helpers ---
# --- MODIFICATION : La fonction ne retourne que des données, sans appeler st.toast ---
@st.cache_data(ttl=3600*24*7)
def get_vendor_from_mac(mac: str) -> tuple[str | None, str | None]:
    """
    Interroge l'API maclookup.app.
    Retourne un tuple (vendor, error_message).
    L'un des deux est toujours None.
    """
    if not mac or len(mac) < 8:
        return None, "Adresse MAC invalide."
    try:
        oui = mac.replace(":", "").replace("-", "").upper()[:6]
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0'
        }
        req = Request(f"https://api.maclookup.app/v2/macs/{oui}/company/name", headers=headers)
        with urlopen(req, timeout=4) as resp:
            vendor = resp.read().decode('utf-8').strip()
            if vendor and vendor not in ["*NO COMPANY*", "*PRIVATE*"]:
                return vendor, None  # Succès
            else:
                return None, "Fabricant non trouvé par l'API."
    except HTTPError as e:
        return None, f"Erreur HTTP {e.code}"
    except Exception as e:
        return None, f"Erreur réseau : {e}"

@st.cache_data(ttl=60)
def get_api_version_info(host: str) -> dict | None:
    if not host: return None
    try:
        with urlopen(f"http://{host}/api_version", timeout=3) as resp:
            return json.load(resp)
    except Exception: return None

def check_ping(ip: str, timeout_sec: int = 1) -> str:
    if not ip: return "N/A"
    try:
        from ping3 import ping as _ping3_ping
        if _ping3_ping(ip, timeout=timeout_sec) is not False: return "✅"
    except Exception: pass
    try:
        param = "-n 1 -w 1000" if platform.system().lower() == "windows" else "-c 1 -W 1"
        command = f"ping {param} {ip}"
        res = subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout_sec + 1)
        return "✅" if res.returncode == 0 else "❌"
    except Exception: return "❌"

# --- Initialisation de l'état de la session ---
if 'fbx_client' not in st.session_state: st.session_state['fbx_client'] = None
if 'lan_df' not in st.session_state: st.session_state['lan_df'] = None
if 'ping_results' not in st.session_state: st.session_state['ping_results'] = {}

# --- Fonctions asynchrones ---
async def open_smart(fbx: Freepybox, attempts: list):
    if not attempts:
        st.error("Aucune méthode de connexion valide n'a pu être déterminée.")
        return
    for host, port, use_https, label in attempts:
        with st.spinner(f"Essai de connexion : {label}..."):
            signatures = [(host, port, use_https), (host, port), (host,)]
            for sig in signatures:
                try:
                    await fbx.open(*sig)
                    st.toast(f"Connecté via {label} !", icon="✅"); return
                except TypeError: continue
                except (ClientConnectorError, ConnectionError, asyncio.TimeoutError):
                    st.warning(f"Échec de la connexion réseau via {label}"); break
    raise ConnectionError("Toutes les tentatives de connexion ont échoué.")

async def get_interfaces_compat(fbx: Freepybox):
    return await fbx.lan.get_interfaces() if hasattr(fbx.lan, "get_interfaces") else await fbx.lan.get_interfaces_list()

async def get_hosts_compat(fbx: Freepybox, iface_name: str):
    return await fbx.lan.get_hosts(iface_name) if hasattr(fbx.lan, "get_hosts") else await fbx.lan.get_hosts_list(iface_name)

async def wake_host(fbx: Freepybox, iface: str, mac: str):
    if not all([fbx, iface, mac]): return False, "Informations manquantes."
    if not hasattr(fbx.lan, "wol"): return False, "Fonction WoL non supportée."
    try:
        await fbx.lan.wol(iface, mac); return True, f"Paquet WoL envoyé à {mac}."
    except Exception as e: return False, f"Erreur WoL : {e}"

async def fetch_all_data(app_desc, attempts):
    if not attempts: return pd.DataFrame()
    fbx = Freepybox(app_desc)
    await open_smart(fbx, attempts)
    st.session_state['fbx_client'] = fbx
    interfaces = await get_interfaces_compat(fbx) or []
    tasks = [get_hosts_compat(fbx, iface.get("name")) for iface in interfaces]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    parts = [df_from_hosts(res, interfaces[i].get("name")) for i, res in enumerate(results) if isinstance(res, list)]
    if not parts: return pd.DataFrame()
    all_df = pd.concat(parts, ignore_index=True)
    return all_df.drop_duplicates(subset=["mac", "name"], keep="first").sort_values(
        by=["reachable", "days_since_last", "name"], ascending=[False, True, True], na_position="last"
    )

async def close_session():
    if st.session_state['fbx_client']:
        try: await st.session_state['fbx_client'].close()
        finally:
            st.session_state['fbx_client'] = None
            st.session_state['lan_df'] = None
            st.session_state['ping_results'] = {}

# --- Helpers données ---
def df_from_hosts(hosts, iface_name):
    rows = []
    now = pd.Timestamp.now(tz="Europe/Paris")
    for h in hosts or []:
        ts, l3 = h.get("last_activity"), h.get("l3connectivities", [])
        last_seen = pd.to_datetime(ts, unit="s", utc=True).tz_convert("Europe/Paris") if ts else pd.NaT
        ipv4 = ", ".join(sorted([c.get("addr") for c in l3 if c.get("addr") and str(c.get("af")) in ("4", "ipv4")]))
        mac = (h.get("l2ident") or {}).get("id")
        vendor = (h.get("l2ident") or {}).get("vendor_name")
        rows.append({
            "interface": iface_name, "name": h.get("primary_name"), "host_type": h.get("host_type"),
            "reachable": h.get("reachable"), "last_activity": last_seen,
            "days_since_last": int((now - last_seen).days) if pd.notna(last_seen) else None,
            "ipv4": ipv4, "mac": mac, "vendor": vendor,
        })
    return pd.DataFrame(rows)

# --- Barre latérale (Sidebar) ---
with st.sidebar:
    st.header("Connexion Freebox")
    if st.session_state.get('fbx_client'):
        st.success("Connecté à la Freebox.")
        if st.button("🔌 Se déconnecter"):
            asyncio.run(close_session()); st.rerun()
    else:
        host_input = st.text_input("Hôte/Domaine", value="mafreebox.freebox.fr")
        port_input = st.number_input("Port HTTPS", value=30476, step=1)
        auto_detect = st.checkbox("Auto-détecter la connexion", value=True)
        st.divider()
        st.header("Identité de l'application")
        app_id = st.text_input("App ID", value="com.fase.app")
        app_name = st.text_input("App Name", value="Freebox API Stats Exporter")
        app_version = st.text_input("App Version", value="3.0")
        device_name = st.text_input("Device Name", value="FASE-Client-Advanced")
        if st.button("🚀 Se connecter / (ré)autoriser", type="primary", use_container_width=True):
            attempts = []
            host = host_input.strip()
            if auto_detect:
                info = get_api_version_info(host)
                if info and (api_domain := info.get("api_domain")) and (https_port := info.get("https_port")):
                    attempts.append((api_domain, int(https_port), True, f"Auto-détecté : {api_domain}"))
                else: st.error("L'auto-détection a échoué.")
            else: attempts.append((host, int(port_input), True, f"Manuel : {host}"))
            app_desc = {"app_id": app_id, "app_name": app_name, "app_version": app_version, "device_name": device_name}
            try:
                with st.spinner("Récupération des données..."):
                    data = asyncio.run(fetch_all_data(app_desc, attempts))
                if not data.empty or st.session_state.get('fbx_client'):
                    st.session_state["lan_df"] = data; st.rerun()
            except AuthorizationError: st.error("🔴 Autorisation refusée. Validez sur l'écran de la Freebox.")
            except (ClientConnectorError, ConnectionError): st.error("🔌 Erreur de connexion réseau.")
            except Exception as e: st.exception(e)
    st.divider()
    st.header("Filtres globaux")
    only_reachable = st.checkbox("Uniquement joignables", value=True)
    q = st.text_input("Recherche (nom, MAC, vendor, IP)...")

# --- Affichage principal ---
if 'lan_df' not in st.session_state or st.session_state['lan_df'] is None:
    st.info("Utilisez le menu latéral pour vous connecter à votre Freebox.")
else:
    df_source = st.session_state['lan_df']
    df = df_source.copy()
    if only_reachable: df = df[df["reachable"] == True]
    if q:
        ql = q.lower()
        df = df[df.apply(lambda row: any(ql in str(row.get(col,"")).lower() for col in ["name", "mac", "vendor", "ipv4"]), axis=1)]

    tab_table, tab_cards, tab_vendor_stats = st.tabs(["📋 Tableau", "🧩 Cartes & Actions", "🔍 Fabricants & Stats"])

    with tab_table:
        st.subheader(f"Appareils affichés ({len(df)} / {len(df_source)})")
        df_display = df.copy()
        if st.button("📡 Lancer un ping sur les appareils affichés"):
            progress_bar = st.progress(0, "Pinging appareils...")
            ping_results = {}
            for i, row in enumerate(df_display.itertuples()):
                first_ip = getattr(row, "ipv4", "").split(",")[0].strip()
                if first_ip: ping_results[row.mac] = check_ping(first_ip)
                progress_bar.progress((i + 1) / len(df_display), f"Pinging {row.name}...")
            st.session_state.ping_results.update(ping_results)
            progress_bar.empty(); st.toast("Ping terminé !")
        if st.session_state.ping_results:
            df_display['ping_status'] = df_display['mac'].map(st.session_state.ping_results).fillna("N/A")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        st.divider()
        c1, c2 = st.columns(2)
        c1.download_button("📥 Exporter en CSV", df_display.to_csv(index=False).encode('utf-8'), 'freebox.csv', 'text/csv', use_container_width=True)
        c2.download_button("📥 Exporter en JSON", df_display.to_json(orient='records').encode('utf-8'), 'freebox.json', 'application/json', use_container_width=True)

    with tab_cards:
        st.subheader("Actions individuelles par appareil")
        if df.empty: st.info("Aucun appareil à afficher avec les filtres actuels.")
        for index, row in df.iterrows():
            mac = row.get('mac')
            is_vendor_known = row.get("vendor") and row.get("vendor").lower() not in ["(unknown)", "unknown", ""]
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{row.get('name','(sans nom)')}** (`{row.get('host_type','?')}`)")
                    st.caption(f"MAC: `{mac}` | IP: `{row.get('ipv4','')}`")
                    
                    vc1, vc2 = st.columns([2,1])
                    with vc1:
                        st.markdown(f"Fabricant : **{row.get('vendor') or '(inconnu)'}**")
                    if not is_vendor_known:
                        with vc2:
                            if st.button("🔍 Chercher", key=f"vendor_{mac}", help="Rechercher le fabricant via l'API"):
                                with st.spinner("Recherche..."):
                                    # --- MODIFICATION : Interprétation du résultat de la fonction ---
                                    new_vendor, error = get_vendor_from_mac(mac)
                                    if new_vendor:
                                        st.session_state.lan_df.loc[st.session_state.lan_df['mac'] == mac, 'vendor'] = new_vendor
                                        st.rerun()
                                    else:
                                        st.toast(error, icon="❌")
                with c2:
                    st.write("")
                    if st.button("Ping 📡", key=f"ping_{mac}"):
                        first_ip = row.get("ipv4", "").split(",")[0].strip()
                        if first_ip: st.toast(f"Ping {row['name']} ({first_ip}): {check_ping(first_ip)}")
                        else: st.toast("Aucune adresse IP à pinger.", icon="⚠️")
                    if not row.get('reachable', False):
                        if st.button("Réveiller ⚡", key=f"wol_{mac}"):
                             with st.spinner("Envoi..."):
                                fbx = st.session_state.get('fbx_client')
                                success, msg = asyncio.run(wake_host(fbx, row.get('interface'), mac))
                                st.toast(msg, icon="✅" if success else "❌")
                    else: st.success("En ligne")

    with tab_vendor_stats:
        st.subheader("Gestion des Fabricants (Vendors)")
        unknown_vendor_df = df_source[
            df_source['vendor'].isnull() |
            df_source['vendor'].str.lower().isin(["(unknown)", "unknown", ""])
        ]
        nb_unknown = len(unknown_vendor_df)
        col1, col2 = st.columns(2)
        col1.metric("Fabricants inconnus", nb_unknown)
        with col2:
            st.write("")
            if st.button("🤖 Enrichir les fabricants inconnus", disabled=nb_unknown == 0, type="primary"):
                progress_bar = st.progress(0, "Recherche des fabricants...")
                updated_count = 0
                for i, row in enumerate(unknown_vendor_df.itertuples()):
                    mac = row.mac
                    progress_bar.progress((i + 1) / nb_unknown, f"Recherche pour {row.name} ({mac})...")
                    # --- MODIFICATION : Interprétation du résultat ici aussi ---
                    new_vendor, error = get_vendor_from_mac(mac)
                    if new_vendor:
                        st.session_state.lan_df.loc[st.session_state.lan_df['mac'] == mac, 'vendor'] = new_vendor
                        updated_count += 1
                progress_bar.empty()
                st.toast(f"{updated_count} fabricant(s) trouvé(s) et mis(es) à jour !", icon="✨")
                st.rerun()

        st.divider()
        st.subheader("Statistiques Générales")
        total, reach = len(df_source), int(df_source['reachable'].fillna(False).sum())
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Appareils connus", total)
        k2.metric("Joignables", reach, f"{(reach / total * 100.0) if total else 0.0:.0f}%")
        k3.metric("Fabricants identifiés", df_source['vendor'].nunique())
        k4.metric("Interfaces", df_source['interface'].nunique())
        st.divider()
        cstats1, cstats2 = st.columns(2)
        with cstats1:
            st.markdown("**Top 10 Fabricants**")
            top_vendors = df_source['vendor'].fillna('(inconnu)').value_counts().head(10).rename_axis('vendor').reset_index(name='count')
            st.bar_chart(top_vendors, x='vendor', y='count')
        with cstats2:
            st.markdown("**Appareils par interface**")
            per_iface = df_source['interface'].fillna('(inconnue)').value_counts().rename_axis('interface').reset_index(name='count')
            st.bar_chart(per_iface, x='interface', y='count')