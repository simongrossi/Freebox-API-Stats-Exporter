# quick_test.py (Freebox API Stats Exporter - generic defaults)
import asyncio
from freebox_api import Freepybox

APP = {
    "app_id": "com.example.fase",
    "app_name": "Freebox API Stats Exporter",
    "app_version": "1.0",
    "device_name": "My-Computer",
}

# HTTPS (recommandé)
HOST_HTTPS = "mafreebox.freebox.fr"  # remplacez si vous avez un domaine fbxos.fr
PORT_HTTPS = 30476

# Fallback autorisation initiale: HTTP local
HOST_HTTP  = "mafreebox.freebox.fr"
PORT_HTTP  = 80

async def open_compat(fbx: Freepybox):
    # 1) host seul
    try:
        await fbx.open(HOST_HTTPS)
        return
    except TypeError:
        pass
    # 2) host + port
    try:
        await fbx.open(HOST_HTTPS, PORT_HTTPS)
        return
    except TypeError:
        pass
    # 3) host + port + https=True
    try:
        await fbx.open(HOST_HTTPS, PORT_HTTPS, True)
        return
    except Exception:
        # 4) HTTP local pour autorisation initiale
        await fbx.open(HOST_HTTP, PORT_HTTP, False)

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

async def main():
    fbx = Freepybox(APP)
    try:
        await open_compat(fbx)
        ifaces = await get_interfaces_compat(fbx)
        names = [i.get("name") for i in (ifaces or [])]
        print("Interfaces:", names)
        if names:
            hosts = await get_hosts_compat(fbx, names[0])
            print(f"Hôtes sur {names[0]} :", len(hosts or []))
    finally:
        try:
            await fbx.close()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
