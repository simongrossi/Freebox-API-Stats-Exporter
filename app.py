# app.py (Freebox API Stats Exporter - Version 2.1 Corrigée)
import asyncio
import json
from urllib.parse import urlparse
from urllib.request import urlopen
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import streamlit as st

from freebox_api import Freepybox
from freebox_api.exceptions import AuthorizationError

# --- Configuration & Constantes ---
st.set_page_config(page_title="Freebox API Stats Exporter", page_icon="📊", layout="wide")
APP_DESC = {
    "app_id": "com.fase.app",
    "app_name": "Freebox API Stats Exporter",
    "app_version": "2.1",
    "device_name": "FASE-Client-Robust",
}
DEFAULT_COLS = ["interface", "name", "host_type", "reachable", "last_activity", "days_since_last", "ipv4", "mac", "vendor"]

# --- Helpers API & Données ---

@st.cache_data(ttl=60)
def get_api_version_info(host: str) -> Optional[Dict[str, Any]]:
    """Appelle http://<host>/api_version et retourne le dict (ou None)."""
    if not host: return None
    try:
        with urlopen(f"http://{host}/api_version", timeout=4) as resp:
            return json.load(resp)
    except Exception:
        return None

def _flatten_ips(l3: Optional[List[Dict]]) -> Tuple[str, str, str]:
    """Gère les formats d'adresse 'af' (str/int) pour extraire les IPs."""
    if not l3: return "", "", ""
    ipv4s = [c["addr"] for c in l3 if str(c.get("af")) in ("4", "ipv4") and c.get("addr")]
    ipv6s = [c["addr"] for c in l3 if str(c.get("af")) in ("6", "ipv6") and c.get("addr")]
    return ", ".join(ipv4s + ipv6s), ", ".join(ipv4s), ", ".join(ipv6s)

def df_from_hosts(hosts: List[Dict], iface_name: str) -> pd.DataFrame:
    """Convertit une liste de hosts JSON en DataFrame Pandas."""
    rows = []
    for h in hosts or []:
        ips_all, ipv4, ipv6 = _flatten_ips(h.get("l3connectivities"))
        ts = h.get("last_activity")
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone() if ts else None
        days_since = (datetime.now(tz=dt.tzinfo) - dt).days if dt else None
        rows.append({
            "interface": iface_name, "name": h.get("primary_name"), "host_type": h.get("host_type"),
            "reachable": h.get("reachable"), "last_activity": dt, "days_since_last": days_since,
            "ipv4": ipv4, "ipv6": ipv6, "ips": ips_all,
            "mac": (h.get("l2ident") or {}).get("id"), "vendor": (h.get("l2ident") or {}).get("vendor_name"), "id": h.get("id"),
        })
    return pd.DataFrame(rows)

# --- Logique de Connexion Asynchrone ---

def resolve_connection_attempts(url: str, host: str, port: int, auto: bool) -> List[Tuple[str, int, bool, str]]:
    """Crée une liste d'essais de connexion intelligente et sans doublons."""
    attempts = []
    if url.strip():
        u = urlparse(url.strip())
        if u.hostname:
            use_https = u.scheme == "https"
            p = u.port or (443 if use_https else 80)
            attempts.append((u.hostname, p, use_https, f"URL: {u.scheme}://{u.hostname}:{p}"))
        return attempts
    if not host.strip(): return []
    if auto and (info := get_api_version_info(host)):
        if (api_domain := info.get("api_domain")) and (https_port := info.get("https_port")):
            attempts.append((api_domain, int(https_port), True, f"Auto: {api_domain}:{https_port}"))
    if port == 80: attempts.append((host, port, False, f"Manuel (HTTP): {host}:{port}"))
    elif port == 443: attempts.append((host, port, True, f"Manuel (HTTPS): {host}:{port}"))
    else: attempts.append((host, port, True, f"Manuel: {host}:{port}"))
    seen = set()
    return [x for x in attempts if not ((x[0], x[1]) in seen or seen.add((x[0], x[1])))]

async def open_smart(fbx: Freepybox, attempts: list, http_fallback: bool) -> Tuple[str, int, str]:
    """Tente de se connecter en essayant plusieurs signatures d'appel pour plus de robustesse."""
    for host, port, use_https, label in attempts:
        with st.status(f"Essai : {label}", expanded=False) as status:
            signatures = [(host, port, use_https), (host, port), (host,)]
            for sig in signatures:
                try:
                    await fbx.open(*sig)
                    status.update(label=f"Succès : {label}", state="complete")
                    return host, port, label
                except (TypeError, ValueError): continue
                except Exception: break
    if http_fallback:
        with st.status("Dernier recours : Fallback HTTP", expanded=False) as status:
            try:
                await fbx.open("mafreebox.freebox.fr", 80, False)
                status.update(label="Succès : Fallback HTTP", state="complete")
                return "mafreebox.freebox.fr", 80, "Fallback HTTP"
            except Exception as e:
                status.update(label="Échec : Fallback HTTP", state="error")
                raise ConnectionError("Le fallback HTTP a échoué.") from e
    raise ConnectionError("Toutes les tentatives de connexion ont échoué.")

async def get_interfaces_compat(fbx: Freepybox) -> list:
    """Gère les différentes versions de nom de méthode pour les interfaces."""
    try: return await fbx.lan.get_interfaces()
    except AttributeError: return await fbx.lan.get_interfaces_list()

async def get_hosts_compat(fbx: Freepybox, iface_name: str) -> list:
    """Gère les différentes versions de nom de méthode pour les hosts."""
    try: return await fbx.lan.get_hosts(iface_name)
    except AttributeError: return await fbx.lan.get_hosts_list(iface_name)

async def fetch_all_data(app_desc, url, host, port, auto, fallback) -> pd.DataFrame:
    """Orchestre la connexion et la récupération des données."""
    fbx = Freepybox(app_desc)
    is_connected = False
    try:
        attempts = resolve_connection_attempts(url, host, port, auto)
        if not attempts and not fallback:
             st.warning("Aucune cible de connexion définie.")
             return pd.DataFrame()

        host_used, port_used, source_label = await open_smart(fbx, attempts, fallback)
        is_connected = True
        st.toast(f"Connecté via {host_used}:{port_used}", icon="✅")

        interfaces = await get_interfaces_compat(fbx) or []
        tasks = [get_hosts_compat(fbx, iface.get("name")) for iface in interfaces]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        parts = []
        for i, res in enumerate(results):
            iface_name = interfaces[i].get("name")
            if isinstance(res, list) and not (df := df_from_hosts(res, iface_name)).empty:
                parts.append(df)
            elif isinstance(res, Exception):
                st.warning(f"Erreur sur l'interface '{iface_name}': {res}")

        if not parts: return pd.DataFrame()
        
        all_df = pd.concat(parts, ignore_index=True)
        
        # Correction du type de la colonne datetime pour éviter les erreurs .dt
        all_df['last_activity'] = pd.to_datetime(all_df['last_activity'], errors='coerce')
        
        return all_df.drop_duplicates(subset=["mac", "name"], keep="first").sort_values(
            by=["reachable", "days_since_last", "name"], ascending=[False, True, True], na_position="last"
        )
    finally:
        if is_connected: await fbx.close()

# --- Interface Utilisateur Streamlit ---
with st.sidebar:
    st.header("Connexion Freebox")
    url_input = st.text_input("URL complète (prioritaire)", help="Ex: https://xxx.fbxos.fr:30476")
    host_input = st.text_input("Hôte/Domaine (si URL vide)", value="mafreebox.freebox.fr")
    port_input = st.number_input("Port (si URL vide)", value=30476, step=1)
    c1, c2 = st.columns(2)
    auto_detect = c1.checkbox("Auto-détecter", value=True, help="Trouver le port via /api_version")
    allow_http_fallback = c2.checkbox("Fallback HTTP", value=True, help="Tente mafreebox.freebox.fr:80 en dernier")
    st.divider()
    with st.expander("Identité de l'application"):
        APP_DESC["app_id"] = st.text_input("App ID", value=APP_DESC["app_id"])
        APP_DESC["app_name"] = st.text_input("App Name", value=APP_DESC["app_name"])
        APP_DESC["app_version"] = st.text_input("App Version", value=APP_DESC["app_version"])
        APP_DESC["device_name"] = st.text_input("Device Name", value=APP_DESC["device_name"])
    st.divider()
    st.header("Options d’affichage")
    default_only_reach = st.checkbox("Uniquement joignables", value=True)
    hide_inactive_days = st.number_input("Masquer inactifs > N jours", value=0, min_value=0)
    selected_cols = st.multiselect("Colonnes à afficher", DEFAULT_COLS + ["ips", "id", "ipv6"], default=DEFAULT_COLS)
    
    if st.button("Se connecter / Actualiser", type="primary", use_container_width=True):
        st.session_state.run_fetch = True

if st.session_state.get("run_fetch", False):
    st.session_state.run_fetch = False
    with st.expander("Logs de connexion", expanded=True):
        with st.spinner("Récupération des données en cours..."):
            try:
                data = asyncio.run(fetch_all_data(APP_DESC, url_input, host_input, int(port_input), auto_detect, allow_http_fallback))
                st.session_state.lan_df = data
                if data.empty and "lan_df" not in st.session_state:
                     st.warning("Aucun appareil trouvé sur le réseau local.")
            except AuthorizationError:
                st.error("Autorisation refusée. Validez la demande sur l'écran de la Freebox, puis relancez.")
            except Exception as e:
                st.error(f"Une erreur est survenue : {e}")

if "lan_df" not in st.session_state or st.session_state.lan_df.empty:
    if "lan_df" not in st.session_state:
        st.info("Cliquez sur 'Se connecter / Actualiser' dans la barre latérale pour commencer.")
else:
    df_source = st.session_state.lan_df
    st.subheader("Filtres")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    mask = pd.Series(True, index=df_source.index)
    if c1.checkbox("Uniquement joignables", value=default_only_reach): mask &= df_source["reachable"]
    if hide_inactive_days > 0: mask &= (df_source["days_since_last"].isna()) | (df_source["days_since_last"] <= hide_inactive_days)
    if iface_filter := c2.multiselect("Interfaces", sorted(df_source["interface"].dropna().unique())): mask &= df_source["interface"].isin(iface_filter)
    if type_filter := c3.multiselect("Types", sorted(df_source["host_type"].dropna().unique())): mask &= df_source["host_type"].isin(type_filter)
    if q := c4.text_input("Recherche (nom/IP/MAC/vendor)…"):
        search_mask = df_source[["name", "ips", "mac", "vendor"]].fillna("").apply(lambda col: col.str.lower().str.contains(q.lower())).any(axis=1)
        mask &= search_mask
    
    df_filtered = df_source[mask]
    st.subheader(f"Appareils affichés ({len(df_filtered)} / {len(df_source)})")
    
    df_display = df_filtered.copy()
    df_display["last_activity"] = df_display["last_activity"].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('')
    
    st.dataframe(df_display[selected_cols], use_container_width=True, hide_index=True)
    csv = df_filtered.to_csv(index=False).encode("utf-8")
    json_str = df_filtered.to_json(orient="records", force_ascii=False, date_format="iso")
    c_exp1, c_exp2 = st.columns(2)
    c_exp1.download_button("💾 Export CSV", data=csv, file_name="freebox_devices.csv", mime="text/csv", use_container_width=True)
    c_exp2.download_button("💾 Export JSON", data=json_str, file_name="freebox_devices.json", mime="application/json", use_container_width=True)