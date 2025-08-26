# app.py (Freebox API Stats Exporter - fixed generic identity)
import asyncio
from datetime import datetime, timezone
import pandas as pd
import streamlit as st

from freebox_api import Freepybox
from freebox_api.exceptions import AuthorizationError, HttpRequestError

st.set_page_config(page_title="Freebox API Stats Exporter", page_icon="📊", layout="wide")
st.title("📊 Freebox API Stats Exporter")
st.caption("Explorer, filtrer et exporter les appareils Freebox — avec vues stats en Streamlit.")

# ---------- Sidebar: Connexion & options ----------
with st.sidebar:
    st.header("Connexion Freebox")
    # Valeurs génériques par défaut
    host_https = st.text_input("Hôte/Domaine", value="mafreebox.freebox.fr")
    port_https = st.number_input("Port HTTPS", value=30476, step=1)
    # Astuce première autorisation : mafreebox.freebox.fr:80 en HTTP si besoin

    st.divider()
    st.header("Identité de l'application")
    # Valeurs fixes génériques pour l'identité de l'application
    app_id = st.text_input("App ID", value="com.fase.app")
    app_name = st.text_input("App Name", value="Freebox API Stats Exporter")
    app_version = st.text_input("App Version", value="1.0")
    device_name = st.text_input("Device Name", value="FASE-Client")

    st.divider()
    st.header("Options d’affichage")
    default_only_reach = st.checkbox("Uniquement joignables par défaut", value=True)
    hide_inactive_days = st.number_input("Masquer inactifs depuis > N jours (0 = désactivé)",
                                         value=0, min_value=0)

    connect_btn = st.button("Se connecter / (ré)autoriser")

# ---------- Helpers (compat signatures/méthodes) ----------
async def open_compat(fbx: Freepybox, host_https: str, port_https: int):
    """Ouvre une session en essayant plusieurs signatures d'open()."""
    try:
        await fbx.open(host_https)
        return
    except TypeError:
        pass
    try:
        await fbx.open(host_https, port_https)
        return
    except TypeError:
        pass
    try:
        await fbx.open(host_https, port_https, True)
        return
    except Exception:
        await fbx.open("mafreebox.freebox.fr", 80, False)

async def get_interfaces_compat(fbx: Freepybox):
    try:
        return await fbx.lan.get_interfaces()
    except AttributeError:
        return await fbx.lan.get_interfaces_list()

async def get_hosts_compat(fbx: Freepybox, iface_name: str):
    try:
        return await fbx.lan.get_hosts(iface_name)
    except AttributeError:
        return await fbx.lan.get_hosts_list(iface_name)

def _flatten_ips(l3):
    if not l3:
        return "", "", ""
    ipv4s = [c.get("addr") for c in l3 if str(c.get("af")) == "4" and c.get("addr")]
    ipv6s = [c.get("addr") for c in l3 if str(c.get("af")) == "6" and c.get("addr")]
    all_ips = ipv4s + ipv6s
    return ", ".join(all_ips), ", ".join(ipv4s), ", ".join(ipv6s)

def _ts_to_dt(ts):
    if ts in (None, "", 0):
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone()
    except Exception:
        return None

def _days_since(dtobj):
    if not dtobj:
        return None
    now = datetime.now(tz=dtobj.tzinfo)
    return (now - dtobj).days

def df_from_hosts(hosts, iface_name):
    rows = []
    for h in hosts or []:
        ips_all, ipv4, ipv6 = _flatten_ips(h.get("l3connectivities"))
        last_seen = _ts_to_dt(h.get("last_activity"))
        rows.append({
            "interface": iface_name,
            "name": h.get("primary_name"),
            "host_type": h.get("host_type"),
            "reachable": h.get("reachable"),
            "last_activity": last_seen,
            "days_since_last": _days_since(last_seen),
            "ipv4": ipv4,
            "ipv6": ipv6,
            "ips": ips_all,
            "mac": (h.get("l2ident") or {}).get("id"),
            "vendor": (h.get("l2ident") or {}).get("vendor_name"),
            "id": h.get("id"),
        })
    cols = ["interface","name","host_type","reachable","last_activity","days_since_last",
            "ipv4","ipv6","ips","mac","vendor","id"]
    return pd.DataFrame(rows).reindex(columns=cols)

async def fetch_all(app_desc, host, port):
    fbx = Freepybox(app_desc)
    try:
        await open_compat(fbx, host, port)
        interfaces = await get_interfaces_compat(fbx) or []
        parts = []
        for iface in interfaces:
            name = iface.get("name")
            try:
                hosts = await get_hosts_compat(fbx, name)
            except HttpRequestError:
                hosts = []
            df = df_from_hosts(hosts, name)
            if not df.empty:
                parts.append(df)
        if parts:
            all_df = pd.concat(parts, ignore_index=True)
            all_df = all_df.drop_duplicates(subset=["interface","mac","ips"], keep="first")
            all_df = all_df.sort_values(
                by=["reachable","days_since_last","name"],
                ascending=[False, True, True],
                na_position="last",
            )
            return all_df
        return pd.DataFrame(columns=["interface","name","host_type","reachable","last_activity",
                                     "days_since_last","ipv4","ipv6","ips","mac","vendor","id"])
    finally:
        try:
            await fbx.close()
        except Exception:
            pass

# ---------- Action: connexion ----------
if connect_btn:
    with st.spinner("Connexion à la Freebox…"):
        try:
            app_desc = {
                "app_id": app_id,
                "app_name": app_name,
                "app_version": app_version,
                "device_name": device_name,
            }
            data = asyncio.run(fetch_all(app_desc, host_https.strip(), int(port_https)))
            st.session_state["lan_df"] = data
            st.success("Connecté ✔")
        except AuthorizationError:
            st.error("Autorisation refusée (valide sur l’écran de la Freebox, puis relance).")
        except Exception as e:
            st.exception(e)

lan_df: pd.DataFrame = st.session_state.get("lan_df")

# ---------- Table + filtres + exports ----------
if lan_df is not None and not lan_df.empty:
    st.subheader("Filtres")
    c1, c2, c3, c4 = st.columns([1,1,1,2])
    with c1:
        only_reachable = st.checkbox("Uniquement joignables", value=default_only_reach)
    with c2:
        iface_filter = st.multiselect("Interfaces", sorted(lan_df["interface"].dropna().unique().tolist()))
    with c3:
        type_filter = st.multiselect("Types (host_type)", sorted(lan_df["host_type"].dropna().unique().tolist()))
    with c4:
        q = st.text_input("Recherche (nom/IP/MAC/vendor)…")

    df = lan_df.copy()

    if only_reachable:
        df = df[df["reachable"] == True]

    if hide_inactive_days > 0:
        df = df[(df["days_since_last"].isna()) | (df["days_since_last"] <= hide_inactive_days)]

    if iface_filter:
        df = df[df["interface"].isin(iface_filter)]

    if type_filter:
        df = df[df["host_type"].isin(type_filter)]

    if q:
        ql = q.lower()
        mask = (
            df["name"].fillna("").str.lower().str.contains(ql) |
            df["ipv4"].fillna("").str.lower().str.contains(ql) |
            df["ipv6"].fillna("").str.lower().str.contains(ql) |
            df["ips"].fillna("").str.lower().str.contains(ql)  |
            df["mac"].fillna("").str.lower().str.contains(ql)  |
            df["vendor"].fillna("").str.lower().str.contains(ql)
        )
        df = df[mask]

    st.subheader(f"Appareils trouvés ({len(df)}/{len(lan_df)})")
    show_df = df.copy()
    show_df["last_activity"] = show_df["last_activity"].apply(
        lambda d: d.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(d) else ""
    )
    st.dataframe(show_df, use_container_width=True, hide_index=True)

    cexp1, cexp2 = st.columns(2)
    with cexp1:
        csv = show_df.to_csv(index=False).encode("utf-8")
        st.download_button("💾 Export CSV", data=csv, file_name="freebox_lan_devices.csv", mime="text/csv")
    with cexp2:
        json_str = show_df.to_json(orient="records", force_ascii=False)
        st.download_button("💾 Export JSON", data=json_str, file_name="freebox_lan_devices.json", mime="application/json")
else:
    st.info("Clique sur **Se connecter / (ré)autoriser** pour récupérer les appareils.")
