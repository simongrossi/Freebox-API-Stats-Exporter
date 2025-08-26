# app.py (Freebox API Stats Exporter - v4.4 : Ajout Export & Amélioration Feedback)
import asyncio
import platform
import subprocess
import json
from urllib.request import urlopen
import pandas as pd
import streamlit as st

from freebox_api import Freepybox
from freebox_api.exceptions import AuthorizationError
from aiohttp import ClientConnectorError

# --- Configuration de la page ---
st.set_page_config(page_title="Freebox API Stats Exporter", page_icon="📊", layout="wide")
st.title("📊 Freebox API Stats Exporter")
st.caption("Explorer, filtrer et exporter les appareils Freebox — tableau, cartes, stats, WoL et ping.")

# --- Helpers (Ping & Détection API) ---
@st.cache_data(ttl=60)
def get_api_version_info(host: str) -> dict | None:
    if not host: return None
    try:
        with urlopen(f"http://{host}/api_version", timeout=3) as resp:
            return json.load(resp)
    except Exception:
        return None

try:
    from ping3 import ping as _ping3_ping
except Exception:
    _ping3_ping = None

@st.cache_data(ttl=60)
def check_ping(ip: str, timeout_sec: int = 1) -> str:
    if not ip: return "N/A"
    
    def _system_ping(ip_addr: str) -> bool:
        try:
            param = "-n 1 -w 1000" if platform.system().lower() == "windows" else "-c 1 -W 1"
            command = f"ping {param} {ip_addr}"
            res = subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout_sec + 1)
            return res.returncode == 0
        except Exception: return False

    if _ping3_ping:
        try:
            if _ping3_ping(ip, timeout=timeout_sec) is not False: return "✅"
        except Exception: pass

    return "✅" if _system_ping(ip) else "❌"

# --- Initialisation de l'état de la session ---
if 'fbx_client' not in st.session_state: st.session_state['fbx_client'] = None
if 'lan_df' not in st.session_state: st.session_state['lan_df'] = None

# --- Fonctions asynchrones ---
async def open_smart(fbx: Freepybox, attempts: list):
    """Tente plusieurs signatures d'appel pour une compatibilité maximale."""
    if not attempts:
        st.error("Aucune méthode de connexion valide n'a pu être déterminée.")
        return

    for host, port, use_https, label in attempts:
        with st.spinner(f"Essai de connexion : {label}..."):
            signatures = [(host, port, use_https), (host, port), (host,)]
            for sig in signatures:
                try:
                    await fbx.open(*sig)
                    st.toast(f"Connecté via {label} !", icon="✅")
                    return
                except TypeError:
                    continue
                except (ClientConnectorError, ConnectionError, asyncio.TimeoutError):
                    st.warning(f"Échec de la connexion réseau via {label}")
                    break
    raise ConnectionError("Toutes les tentatives de connexion ont échoué.")


async def get_interfaces_compat(fbx: Freepybox):
    return await fbx.lan.get_interfaces() if hasattr(fbx.lan, "get_interfaces") else await fbx.lan.get_interfaces_list()

async def get_hosts_compat(fbx: Freepybox, iface_name: str):
    return await fbx.lan.get_hosts(iface_name) if hasattr(fbx.lan, "get_hosts") else await fbx.lan.get_hosts_list(iface_name)

async def wake_host(fbx: Freepybox, iface: str, mac: str):
    if not all([fbx, iface, mac]): return False, "Informations manquantes."
    if not hasattr(fbx.lan, "wol"): return False, "Fonction WoL non supportée."
    try:
        await fbx.lan.wol(iface, mac)
        return True, f"Paquet WoL envoyé à {mac}."
    except Exception as e:
        return False, f"Erreur WoL : {e}"

async def fetch_all_data(app_desc, attempts):
    if not attempts:
        return pd.DataFrame()
        
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

# --- Helpers données ---
def df_from_hosts(hosts, iface_name):
    rows = []
    now = pd.Timestamp.now(tz="Europe/Paris")
    for h in hosts or []:
        ts, l3 = h.get("last_activity"), h.get("l3connectivities", [])
        last_seen = pd.to_datetime(ts, unit="s", utc=True).tz_convert("Europe/Paris") if ts else pd.NaT
        ipv4 = ", ".join(sorted([c.get("addr") for c in l3 if c.get("addr") and str(c.get("af")) in ("4", "ipv4")]))
        rows.append({
            "interface": iface_name, "name": h.get("primary_name"), "host_type": h.get("host_type"),
            "reachable": h.get("reachable"), "last_activity": last_seen,
            "days_since_last": int((now - last_seen).days) if pd.notna(last_seen) else None,
            "ipv4": ipv4, "mac": (h.get("l2ident") or {}).get("id"), "vendor": (h.get("l2ident") or {}).get("vendor_name"),
        })
    return pd.DataFrame(rows)

# --- Barre latérale (Sidebar) ---
with st.sidebar:
    st.header("Connexion Freebox")
    if st.session_state['fbx_client']:
        st.success("Connecté à la Freebox.")
        if st.button("🔌 Se déconnecter"):
            asyncio.run(close_session())
            st.rerun()
    else:
        host_input = st.text_input("Hôte/Domaine", value="mafreebox.freebox.fr")
        port_input = st.number_input("Port HTTPS", value=30476, step=1)
        auto_detect = st.checkbox("Auto-détecter la connexion", value=True, help="Si coché, seule la détection automatique sera tentée.")
        
        st.divider()
        st.header("Identité de l'application")
        app_id = st.text_input("App ID", value="com.fase.app")
        app_name = st.text_input("App Name", value="Freebox API Stats Exporter")
        app_version = st.text_input("App Version", value="2.1")
        device_name = st.text_input("Device Name", value="FASE-Client-Robust")

        if st.button("🚀 Se connecter / (ré)autoriser", type="primary", use_container_width=True):
            attempts = []
            host = host_input.strip()
            
            if auto_detect:
                info = get_api_version_info(host)
                if info and (api_domain := info.get("api_domain")) and (https_port := info.get("https_port")):
                    attempts.append((api_domain, int(https_port), True, f"Auto-détecté : {api_domain}"))
                else:
                    st.error("L'auto-détection a échoué. Vérifiez le nom d'hôte ou décochez la case pour une connexion manuelle.")
            else:
                attempts.append((host, int(port_input), True, f"Manuel : {host}"))

            app_desc = {"app_id": app_id, "app_name": app_name, "app_version": app_version, "device_name": device_name}
            try:
                data = asyncio.run(fetch_all_data(app_desc, attempts))
                if not data.empty or st.session_state['fbx_client']:
                    st.session_state["lan_df"] = data
                    st.rerun()
            except AuthorizationError:
                st.error("🔴 Autorisation refusée. Veuillez valider la demande sur l'écran de la Freebox, puis réessayez.")
            except (ClientConnectorError, ConnectionError):
                st.error("🔌 Erreur de connexion réseau. Vérifiez l'hôte, le port et votre pare-feu.")
            except Exception as e:
                st.exception(e)

    st.divider()
    st.header("Filtres globaux")
    only_reachable = st.checkbox("Uniquement joignables", value=True)
    q = st.text_input("Recherche (nom, MAC, vendor, IP)...")

# --- Affichage principal ---
if st.session_state['lan_df'] is None:
    st.info("Utilisez le menu latéral pour vous connecter à votre Freebox.")
else:
    df_source = st.session_state['lan_df']
    df = df_source.copy()
    if only_reachable: df = df[df["reachable"] == True]
    if q:
        ql = q.lower()
        df = df[df.apply(lambda row: any(ql in str(row.get(col,"")).lower() for col in ["name", "mac", "vendor", "ipv4"]), axis=1)]

    tab_table, tab_cards, tab_stats = st.tabs(["📋 Tableau", "🧩 Cartes", "📈 Stats"])
    with tab_table:
        st.subheader(f"Appareils affichés ({len(df)} / {len(df_source)})")
        df_display = df.copy()
        def _first_ipv4(s: str) -> str: return s.split(",")[0].strip() if s else ""
        df_display["ping_status"] = df_display["ipv4"].apply(lambda s: check_ping(_first_ipv4(s)))
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # --- NOUVEAU : Boutons d'export ---
        st.divider()
        col_export1, col_export2 = st.columns(2)
        with col_export1:
            st.download_button(
                label="📥 Exporter en CSV",
                data=df_display.to_csv(index=False).encode('utf-8'),
                file_name='freebox_devices.csv',
                mime='text/csv',
                use_container_width=True
            )
        with col_export2:
            st.download_button(
                label="📥 Exporter en JSON",
                data=df_display.to_json(orient='records', indent=4).encode('utf-8'),
                file_name='freebox_devices.json',
                mime='application/json',
                use_container_width=True
            )


    with tab_cards:
        st.subheader("Vue Cartes + actions WoL")
        if df.empty: st.info("Aucun appareil à afficher avec les filtres actuels.")
        for _, row in df.iterrows():
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.markdown(f"**{row.get('name','(sans nom)')}** (`{row.get('host_type','?')}`)")
                st.caption(f"MAC: `{row.get('mac','?')}` | Vendor: `{row.get('vendor','?')}`")
            with col2:
                st.markdown(f"IPv4: `{row.get('ipv4','')}`")
                last_seen = row['last_activity'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['last_activity']) else 'Jamais vu'
                st.caption(f"Interface: `{row.get('interface','?')}` | Dernière activité: {last_seen}")
            with col3:
                if not row.get('reachable', False):
                    btn_key = f"wol_{row.get('mac') or row.get('name') or id(row)}"
                    if st.button("⚡ Réveiller", key=btn_key):
                        # --- NOUVEAU : Feedback Spinner WoL ---
                        with st.spinner("Envoi du paquet WoL..."):
                            fbx = st.session_state.get('fbx_client')
                            success, message = asyncio.run(wake_host(fbx, row.get('interface'), row.get('mac')))
                            st.toast(f"✅ {message}" if success else f"❌ {message}")
                else:
                    st.markdown("🟢 **En ligne**")
            st.divider()

    with tab_stats:
        st.subheader("Indicateurs (ensemble complet)")
        total, reach = len(df_source), int(df_source['reachable'].fillna(False).sum())
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Appareils connus", total)
        k2.metric("Joignables", reach, f"{(reach / total * 100.0) if total else 0.0:.0f}%")
        k3.metric("Fournisseurs (vendor)", df_source['vendor'].nunique())
        k4.metric("Interfaces", df_source['interface'].nunique())
        st.divider()
        cstats1, cstats2 = st.columns(2)
        with cstats1:
            st.markdown("**Top 10 Vendors**")
            top_vendors = df_source['vendor'].fillna('(inconnu)').value_counts().head(10).rename_axis('vendor').reset_index(name='count')
            st.bar_chart(top_vendors, x='vendor', y='count', use_container_width=True)
        with cstats2:
            st.markdown("**Appareils par interface**")
            per_iface = df_source['interface'].fillna('(inconnue)').value_counts().rename_axis('interface').reset_index(name='count')
            st.bar_chart(per_iface, x='interface', y='count', use_container_width=True)