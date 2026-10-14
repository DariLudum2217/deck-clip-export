"""
Deck Clip Export: backend for the Decky Loader plugin (formerly Deck Media Gallery).

What it does:
  * scans Steam screenshots (userdata/<id>/760/remote/<appid>/screenshots)
    and Game Recording sessions (userdata/<id>/gamerecordings plus extra folders);
  * joins the DASH segments of a recording (init + chunk-*.m4s) and muxes them
    into a regular .mp4 with ffmpeg, without re-encoding;
  * sends files to other devices in two ways:
      - LocalSend protocol (v2): finds receivers on the local network (multicast,
        network scan, saved devices or a manually entered address), asks the
        receiver to accept and uploads the files;
      - Syncthing (optional): hardlinks the file into a folder synced by Syncthing.
        The plugin can run its own Syncthing and pair receiving devices from Game Mode;
  * "remove copies" deletes the plugin's own files (exported MP4 and the outgoing
    Syncthing copy). Steam originals are never touched. The outgoing copy is hidden
    from Syncthing first (ignore pattern), so the deletion never reaches other devices;
  * can download pinned builds of ffmpeg and Syncthing;
  * serves thumbnails and exported videos to the UI from a tiny token-protected
    HTTP server on 127.0.0.1.

IMPORTANT: Decky runs plugins on the trimmed Python from its PyInstaller build.
Parts of the standard library are missing there (xml, http.server, urllib,
hashlib, ssl may be absent, ...), so this file only uses basic modules. All
requests to LocalSend receivers go through curl, which handles HTTPS with the
receivers' self-signed certificates; the local Syncthing REST API is called over
a plain socket.
"""

import asyncio
import binascii
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time

import decky

HOME = decky.DECKY_USER_HOME
SETTINGS_PATH = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "settings.json")
STATE_PATH = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "state.json")
THUMB_DIR = os.path.join(decky.DECKY_PLUGIN_RUNTIME_DIR, "thumbs")
BIN_DIR = os.path.join(decky.DECKY_PLUGIN_RUNTIME_DIR, "bin")
DOWNLOAD_DIR = os.path.join(decky.DECKY_PLUGIN_RUNTIME_DIR, "download")
# LocalSend identity: receivers (LocalSend 1.18+) require a client certificate,
# and the device fingerprint is the SHA-256 of that certificate
CERT_PATH = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "localsend-cert.pem")
KEY_PATH = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "localsend-key.pem")
# Home of the Syncthing instance run by this plugin
ST_HOME = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "syncthing")

STEAM_ROOTS = [
    os.path.join(HOME, ".local/share/Steam"),
    os.path.join(HOME, ".steam/steam"),
    os.path.join(HOME, ".var/app/com.valvesoftware.Steam/.local/share/Steam"),
]

DEFAULT_SETTINGS = {
    # Where exported MP4 files go
    "export_dir": os.path.join(HOME, "Videos", "Steam Recordings"),
    # Extra recording folders (e.g. when Steam records to an SD card)
    "extra_recording_dirs": [],
    # Remove the plugin's copies once a file has been sent (LocalSend) or another
    # device has received it in full (Syncthing)
    "auto_delete": False,
    # Syncthing: optional second way of sending
    "syncthing_enabled": False,
    "outbox_dir": os.path.join(HOME, "Sync", "Deck Clip Export"),
    "per_game_folders": False,
    # Syncthing run by this plugin (only when no other Syncthing is installed)
    "st_managed": False,
    "st_port": 0,
    "st_key": "",
    # Gallery layout: "days" or "grid"; tile width in px
    "ui_layout": "days",
    "ui_tile": 196,
    # LocalSend identity of this device and the receivers it has sent to
    "ls_fingerprint": "",
    "ls_known": [],
    "ls_last": "",
}

# Pinned downloads. Hashes were checked against the builds this plugin was tested with.
BINARIES = {
    "ffmpeg": {
        "url": "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-linux-x64.gz",
        "sha256": "bfe8a8fc511530457b528c48d77b5737527b504a3797a9bc4866aeca69c2dffa",
        "size": 29354986,
        "format": "gz",
        "member": None,
    },
    "syncthing": {
        "url": "https://github.com/syncthing/syncthing/releases/download/v2.1.6/syncthing-linux-amd64-v2.1.6.tar.gz",
        "sha256": "524ef4e1df1850b719e2378c8369956f4e5f2ab9a46fdf7f45f2b925012147aa",
        "size": 11788735,
        "format": "tgz",
        "member": "syncthing-linux-amd64-v2.1.6/syncthing",
    },
}

FOLDER_LABEL = "Deck Clip Export"

LS_PORT = 53317
LS_GROUP = "224.0.0.167"
LS_API = "/api/localsend/v2"

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".mp4": "video/mp4"}
CLIP_RE = re.compile(r"(?:clip|bg|fg|timeline)_(\d+)_(\d{8})_(\d{6})")
CHUNK_RE = re.compile(r"chunk-stream(\d+)-(\d+)\.m4s$")
INIT_RE = re.compile(r"init-stream(\d+)\.m4s$")
DUR_RE = re.compile(r"PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?")


# ---------------------------------------------------------------- i18n

STRINGS = {
    "ru": {
        "ffmpeg_missing": "ffmpeg не найден. Установить его можно в разделе «Настройка».",
        "no_data": "Запись не содержит данных",
        "ffmpeg_failed": "ffmpeg: {err}",
        "stage_concat": "Объединение фрагментов {i}/{n}",
        "stage_mux": "Сборка MP4 {i}/{n}",
        "stage_merge": "Объединение сессий",
        "stage_waiting": "Ожидание подтверждения на устройстве {name}",
        "stage_sending": "Отправка {pct}%",
        "stage_delete": "Удаление копий",
        "nothing_to_delete": "Нет копий для удаления",
        "st_not_found": "Syncthing не найден",
        "st_not_running": "Syncthing установлен, но не запущен",
        "st_no_folder": "Папка для отправки не добавлена в Syncthing",
        "st_ok": "Отправка через папку «{label}»",
        "st_disabled": "Отправка через Syncthing выключена",
        "st_unavailable": "Отправка через Syncthing недоступна: {msg}",
        "stage_outbox": "Копирование в папку Syncthing",
        "stage_hide": "Исключение файла из синхронизации",
        "st_down_delete": "Syncthing не запущен. Удаление копии сейчас привело бы к удалению файла и на других устройствах.",
        "outside_folder": "Файл находится вне папки Syncthing. Удаление отменено.",
        "ignores_get": "Syncthing не вернул список исключений (HTTP {code})",
        "ignores_post": "Syncthing не принял список исключений (HTTP {code})",
        "ignore_unconfirmed": "Syncthing не подтвердил исключение файла из синхронизации. Удаление отменено, чтобы сохранить файл на других устройствах.",
        "stage_start": "Запуск Syncthing",
        "st_other_exists": "Syncthing уже установлен. Повторная установка не требуется.",
        "st_start_failed": "Не удалось запустить Syncthing. Подробности: {log}",
        "st_api": "Syncthing вернул ошибку (HTTP {code})",
        "ls_unreachable": "Устройство {name} недоступно. Убедитесь, что LocalSend открыт и оба устройства находятся в одной сети.",
        "ls_tls": "Не удалось установить защищённое соединение с устройством {name}: {err}",
        "ls_pin": "Устройство {name} требует PIN-код, или указанный PIN-код неверен.",
        "ls_rejected": "Передача отклонена на устройстве {name}.",
        "ls_busy": "Устройство {name} занято другой передачей.",
        "ls_too_many": "Слишком много запросов. Повторите попытку позже.",
        "ls_no_response": "Устройство {name} не ответило на запрос.",
        "ls_error": "Устройство {name} вернуло ошибку (HTTP {code}).",
        "ls_failed": "Ошибка передачи: {err}",
        "ls_not_found": "По адресу {host} не найдено устройство с LocalSend. Убедитесь, что приложение открыто.",
        "not_found_refresh": "Файл не найден. Обновите галерею.",
        "stage_download": "Загрузка {pct}%",
        "stage_verify": "Проверка файла",
        "stage_unpack": "Распаковка",
        "download_failed": "Не удалось загрузить: {err}",
        "bad_checksum": "Загруженный файл повреждён (контрольная сумма не совпадает). Повторите попытку.",
        "binary_broken": "Загруженная программа не запускается",
        "unknown_component": "Неизвестный компонент",
    },
    "en": {
        "ffmpeg_missing": "ffmpeg not found. It can be installed in Setup.",
        "no_data": "The recording contains no data",
        "ffmpeg_failed": "ffmpeg: {err}",
        "stage_concat": "Joining segments {i}/{n}",
        "stage_mux": "Building MP4 {i}/{n}",
        "stage_merge": "Merging sessions",
        "stage_waiting": "Waiting for {name} to accept",
        "stage_sending": "Sending {pct}%",
        "stage_delete": "Removing copies",
        "nothing_to_delete": "No copies to remove",
        "st_not_found": "Syncthing not found",
        "st_not_running": "Syncthing is installed but not running",
        "st_no_folder": "The outgoing folder has not been added to Syncthing",
        "st_ok": "Sending via folder “{label}”",
        "st_disabled": "Sending via Syncthing is turned off",
        "st_unavailable": "Sending via Syncthing is unavailable: {msg}",
        "stage_outbox": "Copying to the Syncthing folder",
        "stage_hide": "Excluding the file from sync",
        "st_down_delete": "Syncthing is not running. Removing the copy now would also delete the file on other devices.",
        "outside_folder": "The file is outside the Syncthing folder. Removal was cancelled.",
        "ignores_get": "Syncthing did not return the ignore list (HTTP {code})",
        "ignores_post": "Syncthing rejected the ignore list (HTTP {code})",
        "ignore_unconfirmed": "Syncthing did not confirm that the file was excluded from sync. Removal was cancelled to keep the file on other devices.",
        "stage_start": "Starting Syncthing",
        "st_other_exists": "Syncthing is already installed. A second installation is not required.",
        "st_start_failed": "Could not start Syncthing. Details: {log}",
        "st_api": "Syncthing returned an error (HTTP {code})",
        "ls_unreachable": "{name} is not reachable. Make sure LocalSend is open and both devices are on the same network.",
        "ls_tls": "Could not establish a secure connection with {name}: {err}",
        "ls_pin": "{name} requires a PIN, or the PIN entered is incorrect.",
        "ls_rejected": "The transfer was declined on {name}.",
        "ls_busy": "{name} is busy with another transfer.",
        "ls_too_many": "Too many requests. Try again later.",
        "ls_no_response": "{name} did not respond to the request.",
        "ls_error": "{name} returned an error (HTTP {code}).",
        "ls_failed": "Transfer failed: {err}",
        "ls_not_found": "No LocalSend device found at {host}. Make sure the app is open.",
        "not_found_refresh": "File not found. Refresh the gallery.",
        "stage_download": "Downloading {pct}%",
        "stage_verify": "Verifying",
        "stage_unpack": "Unpacking",
        "download_failed": "Download failed: {err}",
        "bad_checksum": "The downloaded file is corrupted (checksum mismatch). Try again.",
        "binary_broken": "The downloaded program does not run",
        "unknown_component": "Unknown component",
    },
}

LANG = {"code": "en"}


def T(key, **kw):
    table = STRINGS.get(LANG["code"]) or STRINGS["en"]
    text = table.get(key) or STRINGS["en"].get(key) or key
    return text.format(**kw) if kw else text


class UserError(RuntimeError):
    """An error whose message is meant for the user (already translated)."""


# ---------------------------------------------------------------- utils

def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _expand(p):
    if not p:
        return p
    p = p.strip()
    if p == "~" or p.startswith("~/"):
        p = HOME + p[1:]  # Decky's HOME, not the process environment
    return os.path.realpath(p)


def _safe_name(name, fallback="Unknown"):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", name or "").strip(" .")
    return (name or fallback)[:80]


def _clean_env():
    """Decky is a PyInstaller build and sets its own LD_LIBRARY_PATH, which can
    break system binaries. Restore the original one for child processes."""
    env = os.environ.copy()
    orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if orig:
        env["LD_LIBRARY_PATH"] = orig
    else:
        env.pop("LD_LIBRARY_PATH", None)
    env.setdefault("HOME", HOME)
    return env


def _executable(p):
    return bool(p) and os.path.isfile(p) and os.access(p, os.X_OK)


def _find_ffmpeg():
    candidates = [
        shutil.which("ffmpeg"),
        "/usr/bin/ffmpeg",
        os.path.join(HOME, ".local/bin/ffmpeg"),
        "/home/linuxbrew/.linuxbrew/bin/ffmpeg",
        os.path.join(BIN_DIR, "ffmpeg"),
    ]
    for c in candidates:
        if _executable(c):
            return c
    return None


def _own_binary(name):
    p = os.path.join(BIN_DIR, name)
    return p if _executable(p) else None


def _unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 2
    while os.path.exists(f"{base}_{i}{ext}"):
        i += 1
    return f"{base}_{i}{ext}"


def _new_id(n=8):
    return os.urandom(n).hex()


def _stable_id(text):
    """64-bit FNV-1a: a stable id without hashlib."""
    h = 0xcbf29ce484222325
    for b in text.encode("utf-8", "surrogateescape"):
        h = ((h ^ b) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def _q(text):
    """URL-encode a query value (no urllib)."""
    out = []
    for b in str(text).encode("utf-8"):
        c = chr(b)
        out.append(c if c.isascii() and (c.isalnum() or c in "-_.~") else "%%%02X" % b)
    return "".join(out)


def _xml_unescape(v):
    return (v.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
             .replace("&apos;", "'").replace("&#39;", "'").replace("&amp;", "&"))


ATTR_RE = re.compile(r'([\w:.-]+)\s*=\s*"([^"]*)"')


def _tags(text, name):
    """All opening tags <name ...> as (attribute dict, end position)."""
    out = []
    for m in re.finditer(r"<(?:\w+:)?" + name + r"\b([^>]*)>", text):
        attrs = {k.split(":")[-1]: _xml_unescape(v) for k, v in ATTR_RE.findall(m.group(1))}
        out.append((attrs, m.end()))
    return out


def _parse_duration(s):
    m = DUR_RE.fullmatch(s or "")
    if not m or not any(m.groups()):
        return None
    h, mi, se = (float(x) if x else 0.0 for x in m.groups())
    return h * 3600 + mi * 60 + se


# ---------------------------------------------------------------- DASH sessions

def _session_info(session_dir):
    """Parses session.mpd: which streams exist, which one is video, codec, duration."""
    info = {"streams": [], "video": None, "hevc": False, "duration": None}
    files = os.listdir(session_dir)
    info["streams"] = sorted(int(m.group(1)) for f in files if (m := INIT_RE.match(f)))
    try:
        with open(os.path.join(session_dir, "session.mpd"), "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        mpd = _tags(text, "MPD")
        if mpd:
            info["duration"] = _parse_duration(mpd[0][0].get("mediaPresentationDuration"))
        sets = _tags(text, "AdaptationSet")
        reps = _tags(text, "Representation")
        for attrs, pos in reps:
            parent = None
            for sa, spos in sets:
                if spos <= pos:
                    parent = sa
            kind = (parent or {}).get("contentType") or attrs.get("mimeType", "").split("/")[0]
            if kind == "video" and info["video"] is None:
                try:
                    info["video"] = int(attrs.get("id", "0"))
                except ValueError:
                    pass
                info["hevc"] = attrs.get("codecs", "").startswith(("hev1", "hvc1"))
    except Exception:
        pass
    if info["video"] is None and info["streams"]:
        info["video"] = info["streams"][0]
    return info


def _chunks(session_dir, sid):
    out = []
    for f in os.listdir(session_dir):
        m = CHUNK_RE.match(f)
        if m and int(m.group(1)) == sid:
            out.append((int(m.group(2)), os.path.join(session_dir, f)))
    return [p for _, p in sorted(out)]


def _concat_stream(session_dir, sid, out_path, limit=None):
    parts = [os.path.join(session_dir, f"init-stream{sid}.m4s")] + _chunks(session_dir, sid)
    if limit:
        parts = parts[: limit + 1]
    with open(out_path, "wb") as out:
        for p in parts:
            try:
                with open(p, "rb") as f:
                    shutil.copyfileobj(f, out, 1 << 20)
            except FileNotFoundError:
                # background recording is a ring buffer, old chunks may vanish
                continue


# ---------------------------------------------------------------- network helpers

def _host(h):
    return f"[{h}]" if ":" in h else h


CLIENT_CERT = {"args": []}  # curl options with this device's certificate, once created


def _sha256_hex(data):
    r = subprocess.run(["sha256sum"], input=data, capture_output=True, env=_clean_env(), timeout=10)
    return r.stdout.split()[0].decode().upper()


def _cert_fingerprint(path):
    with open(path, "r", encoding="ascii") as f:
        m = re.search(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", f.read(), re.S)
    if not m:
        raise ValueError("no certificate")
    return _sha256_hex(binascii.a2b_base64("".join(m.group(1).split())))


def _ensure_identity():
    """Creates the self-signed RSA-2048 certificate LocalSend devices identify each
    other by (same parameters as the LocalSend apps). Returns its fingerprint."""
    if os.path.isfile(CERT_PATH) and os.path.isfile(KEY_PATH):
        try:
            return _cert_fingerprint(CERT_PATH)
        except Exception:
            pass
    openssl = shutil.which("openssl") or "/usr/bin/openssl"
    os.makedirs(os.path.dirname(CERT_PATH), exist_ok=True)
    cert_tmp, key_tmp = CERT_PATH + ".new", KEY_PATH + ".new"
    base = [openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256",
            "-keyout", key_tmp, "-out", cert_tmp, "-subj", "/CN=LocalSend User"]
    # A validity starting in the past keeps the certificate valid on receivers
    # whose clock is behind; older OpenSSL versions lack -not_before.
    for extra in (["-not_before", "20000101000000Z", "-not_after", "40960101000000Z"], ["-days", "36500"]):
        r = subprocess.run(base + extra, capture_output=True, env=_clean_env(), timeout=60)
        if r.returncode == 0 and os.path.isfile(cert_tmp):
            break
    else:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip()[-300:])
    os.chmod(key_tmp, 0o600)
    os.replace(key_tmp, KEY_PATH)
    os.replace(cert_tmp, CERT_PATH)
    return _cert_fingerprint(CERT_PATH)


def _curl_json(method, url, payload=None, timeout=10, connect_timeout=5, headers=None):
    """JSON request through curl (-k: LocalSend receivers use self-signed certificates).
    Returns (status, parsed body or None, error text). Status 0 means no connection."""
    cmd = ["curl", "-k", *CLIENT_CERT["args"], "-sS", "--connect-timeout", str(connect_timeout), "-m", str(timeout),
           "-X", method, "-H", "Expect:", "-w", "\n%{http_code}"]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    data = None
    if payload is not None:
        cmd += ["-H", "Content-Type: application/json", "--data-binary", "@-"]
        data = json.dumps(payload).encode("utf-8")
    cmd.append(url)
    try:
        r = subprocess.run(cmd, input=data, capture_output=True, timeout=timeout + 10, env=_clean_env())
    except subprocess.TimeoutExpired:
        return 0, None, "timeout"
    except OSError as e:
        return 0, None, str(e)
    out = r.stdout.decode("utf-8", "replace")
    body, _, code = out.rpartition("\n")
    try:
        status = int(code.strip())
    except ValueError:
        status = 0
    parsed = None
    if body.strip():
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = None
    err = ""
    if r.returncode != 0:
        lines = r.stderr.decode("utf-8", "replace").strip().splitlines()
        err = lines[-1] if lines else f"curl {r.returncode}"
    return status, parsed, err


def _local_ipv4():
    """[(address, prefix length)] of this device's IPv4 interfaces."""
    out = []
    ip_bin = shutil.which("ip") or next((p for p in ("/usr/sbin/ip", "/sbin/ip", "/usr/bin/ip") if _executable(p)), "ip")
    try:
        r = subprocess.run([ip_bin, "-4", "-o", "addr", "show", "scope", "global"],
                           capture_output=True, text=True, timeout=3, env=_clean_env())
        for m in re.finditer(r"inet (\d+\.\d+\.\d+\.\d+)/(\d+)", r.stdout):
            out.append((m.group(1), int(m.group(2))))
    except Exception:
        pass
    if not out:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))  # no packet is sent
            out.append((s.getsockname()[0], 24))
            s.close()
        except OSError:
            pass
    return out


def _gateways():
    """Default IPv4 gateways. When the handheld uses a phone's hotspot, the
    gateway is the phone itself."""
    out = []
    try:
        with open("/proc/net/route", "r") as f:
            next(f, None)
            for line in f:
                parts = line.split()
                if len(parts) > 2 and parts[1] == "00000000" and parts[2] != "00000000":
                    g = bytes.fromhex(parts[2])[::-1]
                    ip = ".".join(str(b) for b in g)
                    if ip not in out:
                        out.append(ip)
    except OSError:
        pass
    return out


def _mime(path):
    return MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream")


# ---------------------------------------------------------------- Syncthing helpers

def _link_or_copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.link(src, dst)  # same filesystem: no extra space used
    except OSError:
        shutil.copy2(src, dst)


def _inner(text, name, start=0):
    m = re.compile(r"<" + name + r"\b[^>]*>(.*?)</" + name + r">", re.S).search(text, start)
    return _xml_unescape(m.group(1).strip()) if m else None


def _http(base, method, path, headers=None, body=None, timeout=4.0):
    """Minimal socket HTTP client (urllib may be missing in Decky's Python).
    Uses HTTP/1.0 so the server never answers chunked. Returns (status, body)."""
    scheme, _, hostport = base.partition("://")
    if hostport.startswith("["):
        host, _, rest = hostport[1:].partition("]")
        port = int(rest.lstrip(":") or (443 if scheme == "https" else 80))
    else:
        host, _, p = hostport.rpartition(":")
        if not host:
            host, p = hostport, ""
        port = int(p or (443 if scheme == "https" else 80))
    payload = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    payload = payload or b""
    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        if scheme == "https":
            import ssl  # only needed for a Syncthing GUI with TLS enabled
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = ctx.wrap_socket(sock, server_hostname=host)
        lines = [f"{method} {path} HTTP/1.0", f"Host: {hostport}", f"Content-Length: {len(payload)}"]
        if payload:
            lines.append("Content-Type: application/json")
        lines += [f"{k}: {v}" for k, v in (headers or {}).items()]
        sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode() + payload)
        data = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
            if len(data) > 8 << 20:
                break
    finally:
        sock.close()
    status = int(data.split(b" ", 2)[1])
    return status, data.split(b"\r\n\r\n", 1)[-1]


def _ignore_pattern(rel):
    """Exact path from the folder root in .stignore syntax, special characters escaped."""
    rel = rel.replace(os.sep, "/")
    return "/" + re.sub(r"([\\*?\[\]{}])", r"\\\1", rel)


def _port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _managed():
    """Connection data of the Syncthing instance run by this plugin, if any."""
    s = core.settings
    if s.get("st_managed") and s.get("st_port") and s.get("st_key"):
        return {"base": f"http://127.0.0.1:{s['st_port']}", "key": s["st_key"],
                "config": os.path.join(ST_HOME, "config.xml")}
    return None


def _syncthing_configs():
    paths = [
        os.path.join(HOME, ".local/state/syncthing/config.xml"),
        os.path.join(HOME, ".config/syncthing/config.xml"),
        os.path.join(ST_HOME, "config.xml"),
    ]
    flatpaks = os.path.join(HOME, ".var/app")
    if os.path.isdir(flatpaks):
        for app in os.listdir(flatpaks):
            for sub in ("config/syncthing", ".local/state/syncthing", "data/syncthing"):
                paths.append(os.path.join(flatpaks, app, sub, "config.xml"))
    # Syncthing started by a Decky plugin (e.g. decky-syncthing, or this plugin)
    for base in (os.path.join(HOME, "homebrew/settings"), os.path.join(HOME, "homebrew/data")):
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            if dirpath[len(base):].count(os.sep) >= 3:
                dirnames[:] = []
            if "config.xml" in filenames:
                paths.append(os.path.join(dirpath, "config.xml"))
    seen, out = set(), []
    for p in paths:
        rp = os.path.realpath(p)
        if os.path.isfile(rp) and rp not in seen:
            seen.add(rp)
            out.append(rp)
    return out


def _parse_syncthing_config(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    gui = _tags(text, "gui")
    if not gui:
        return None
    gattrs, gpos = gui[0]
    addr = (_inner(text, "address", gpos) or "127.0.0.1:8384").replace("0.0.0.0", "127.0.0.1")
    if addr.startswith("/"):
        return None  # unix socket, not supported
    return {
        "base": ("https" if gattrs.get("tls") == "true" else "http") + "://" + addr,
        "key": _inner(text, "apikey", gpos) or "",
        "folders": [a for a, _ in _tags(text, "folder") if a.get("path")],
    }


def _ping(base, key):
    try:
        status, _ = _http(base, "GET", "/rest/system/ping", {"X-API-Key": key}, timeout=2.0)
        return status == 200
    except Exception:
        return False


def _syncthing_status(outbox):
    st = {"found": False, "running": False, "managed": False, "folder_id": None, "folder_label": None,
          "outbox_shared": False, "message": T("st_not_found")}
    outbox = _expand(outbox)
    managed = _managed()
    managed_cfg = os.path.realpath(managed["config"]) if managed else None
    own_home = os.path.realpath(ST_HOME) + os.sep
    best = None
    for cfg_path in _syncthing_configs():
        is_managed = cfg_path == managed_cfg
        if not is_managed and cfg_path.startswith(own_home):
            continue  # our own config while not marked managed: ignore it
        try:
            cfg = _parse_syncthing_config(cfg_path)
        except Exception:
            cfg = None
        if not cfg:
            continue
        if is_managed:
            cfg["base"], cfg["key"] = managed["base"], managed["key"]
        folder = None
        for fo in cfg["folders"]:
            fpath = _expand(fo["path"])
            if fpath and (outbox == fpath or outbox.startswith(fpath.rstrip("/") + "/")):
                folder = fo
                break
        running = _ping(cfg["base"], cfg["key"])
        score = (running, folder is not None, is_managed)
        if best is None or score > best[0]:
            best = (score, cfg, folder, running, is_managed)

    if best is None and managed:
        # managed instance without a config file yet (first start in progress)
        running = _ping(managed["base"], managed["key"])
        best = ((running, False, True), {"base": managed["base"], "key": managed["key"], "folders": []},
                None, running, True)

    if best:
        _, cfg, folder, running, is_managed = best
        st.update(found=True, running=running, managed=is_managed, _base=cfg["base"], _key=cfg["key"])
        if folder:
            st.update(outbox_shared=True, folder_id=folder.get("id"),
                      folder_label=folder.get("label") or folder.get("id"),
                      _folder_root=_expand(folder["path"]))
        if not running:
            st["message"] = T("st_not_running")
        elif not folder:
            st["message"] = T("st_no_folder")
        else:
            st["message"] = T("st_ok", label=st["folder_label"])
    return st


def _public(st):
    return {k: v for k, v in st.items() if not k.startswith("_")}


# ---------------------------------------------------------------- Syncthing REST helpers

IGNORE_HEADERS = (
    "// Deck Clip Export: removed from this device but kept on the others. Do not delete these lines.",
    "// Deck Media Gallery: removed from this device but kept on the others. Do not delete these lines.",
    "// Deck Media Gallery: удалено с GPD, но остаётся на телефоне. Не удаляй эти строки.",
)


def _st_call(st, method, path, body=None):
    status, raw = _http(st["_base"], method, path, {"X-API-Key": st.get("_key", "")}, body)
    data = None
    if raw.strip():
        try:
            data = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            data = None
    return status, data


def _st_ok(st, method, path, body=None):
    status, data = _st_call(st, method, path, body)
    if status >= 300:
        raise UserError(T("st_api", code=status))
    return data


def _st_file(st, rel):
    status, data = _st_call(st, "GET", f"/rest/db/file?folder={_q(st['folder_id'])}&file={_q(rel)}")
    return status, (data if isinstance(data, dict) else {})


def _entry_ignored(entry):
    entry = entry or {}
    # v2 uses "ignored", v1 "invalid"; bit 2 of localFlags means ignored
    return bool(entry.get("ignored") or entry.get("invalid") or (int(entry.get("localFlags") or 0) & 2))


def _st_my_id(st):
    data = _st_ok(st, "GET", "/rest/system/status")
    return (data or {}).get("myID")


def _st_on_remote(st, rel, my_id):
    """True when at least one other device has the complete file."""
    status, info = _st_file(st, rel)
    if status != 200:
        return False
    local, glob = info.get("local") or {}, info.get("global") or {}
    if local.get("deleted") or glob.get("deleted") or _entry_ignored(local) or local.get("version") != glob.get("version"):
        return False
    return any(a.get("id") and a.get("id") != my_id for a in (info.get("availability") or []))


def _st_protect(st, rel, timeout=20.0):
    """Adds the file to Syncthing's ignore list on this device and waits until
    Syncthing applies it. Deleting an ignored file is not announced to other
    devices, so their copies stay."""
    fid = _q(st["folder_id"])
    status, data = _st_call(st, "GET", f"/rest/db/ignores?folder={fid}")
    if status != 200:
        raise UserError(T("ignores_get", code=status))
    lines = list((data or {}).get("ignore") or [])
    pattern = _ignore_pattern(rel)
    if pattern not in lines:
        if not any(h in lines for h in IGNORE_HEADERS):
            lines.append(IGNORE_HEADERS[0])
        lines.append(pattern)
        status, _ = _st_call(st, "POST", f"/rest/db/ignores?folder={fid}", {"ignore": lines})
        if status != 200:
            raise UserError(T("ignores_post", code=status))
    _st_call(st, "POST", f"/rest/db/scan?folder={fid}&sub={_q(rel)}")

    deadline, missing = time.time() + timeout, 0
    while time.time() < deadline:
        status, info = _st_file(st, rel)
        if status == 200 and _entry_ignored(info.get("local")):
            return
        if status == 404:
            missing += 1
            if missing >= 3:  # Syncthing does not know the file and already ignores the path
                return
        else:
            missing = 0
        time.sleep(1)
    raise UserError(T("ignore_unconfirmed"))



# ---------------------------------------------------------------- rename

OLD_NAME = "deck-media-gallery"  # folder name of this plugin before it was renamed


def _migrate_old_name():
    """On the first start under the new name, takes over the settings, the LocalSend
    identity, the Syncthing configuration and the downloaded programs of
    "Deck Media Gallery", so nothing has to be set up again."""
    settings_dir = decky.DECKY_PLUGIN_SETTINGS_DIR.rstrip("/")
    old_settings = os.path.join(os.path.dirname(settings_dir), OLD_NAME)
    old_runtime = os.path.join(os.path.dirname(decky.DECKY_PLUGIN_RUNTIME_DIR.rstrip("/")), OLD_NAME)
    if os.path.realpath(old_settings) == os.path.realpath(settings_dir):
        return
    if os.path.exists(SETTINGS_PATH) or not os.path.isfile(os.path.join(old_settings, "settings.json")):
        return
    old = _load_json(os.path.join(old_settings, "settings.json"), {})
    # stop the old Syncthing first, so its database is copied in a consistent state
    if old.get("st_managed") and old.get("st_port") and old.get("st_key"):
        base = f"http://127.0.0.1:{old['st_port']}"
        if _ping(base, old["st_key"]):
            try:
                _http(base, "POST", "/rest/system/shutdown", {"X-API-Key": old["st_key"]})
            except Exception:
                pass
            for _ in range(30):
                if not _ping(base, old["st_key"]):
                    break
                time.sleep(0.5)
    shutil.copytree(old_settings, settings_dir, symlinks=True, dirs_exist_ok=True)
    old_bin = os.path.join(old_runtime, "bin")
    if os.path.isdir(old_bin):
        shutil.copytree(old_bin, BIN_DIR, dirs_exist_ok=True)
    decky.logger.info(f"settings taken over from {old_settings}")


# ---------------------------------------------------------------- core

class Core:
    def __init__(self):
        raw = _load_json(SETTINGS_PATH, {})
        self.settings = {**DEFAULT_SETTINGS, **raw}
        self.state = _load_json(STATE_PATH, {})
        for key in ("exported", "sent", "offloaded", "paths"):
            self.state.setdefault(key, {})
        # outgoing copies that were removed: their names stay ignored in Syncthing
        # and must never be reused
        self.state.setdefault("retired", [])
        if "syncthing_enabled" not in raw and (raw.get("st_managed") or self.state["sent"]):
            self.settings["syncthing_enabled"] = True  # upgrade from 1.x, which always used Syncthing
            self.save_settings()
        try:
            fingerprint = _ensure_identity()
            CLIENT_CERT["args"] = ["--cert", CERT_PATH, "--key", KEY_PATH]
        except Exception as e:
            decky.logger.warning(f"LocalSend certificate unavailable: {e}")
            fingerprint = self.settings.get("ls_fingerprint") or _new_id(16).upper()
        if self.settings.get("ls_fingerprint") != fingerprint:
            self.settings["ls_fingerprint"] = fingerprint
            self.save_settings()
        self.index = {}  # id -> item (with paths, never sent to the UI)
        self.lock = threading.Lock()
        self.thumb_lock = threading.Semaphore(2)
        self.seen = {}  # LocalSend fingerprint -> device (with "seen" timestamp)
        self.seen_lock = threading.Lock()
        self.stop = threading.Event()
        self.token = _new_id(16)
        self.port = 0
        self.server = None
        self.queue = None
        self.jobs = {}
        self.tasks = []
        self.st_lock = threading.Lock()
        self.pending_delete = set()

    def save_settings(self):
        _save_json(SETTINGS_PATH, self.settings)

    # ---------- migration

    def migrate(self):
        changed = False
        for key in ("delete_original",):  # options of earlier versions
            if key in self.settings:
                self.settings.pop(key)
                changed = True
        if changed:
            self.save_settings()
        if self.state.pop("delivered", None) is not None:
            _save_json(STATE_PATH, self.state)

    # ---------- scanning

    def userdata_dirs(self):
        seen, out = set(), []
        for root in STEAM_ROOTS:
            ud = os.path.join(root, "userdata")
            if not os.path.isdir(ud):
                continue
            for uid in os.listdir(ud):
                p = os.path.realpath(os.path.join(ud, uid))
                if uid.isdigit() and uid != "0" and p not in seen and os.path.isdir(p):
                    seen.add(p)
                    out.append(p)
        return out

    def recording_roots(self):
        roots = [os.path.join(u, "gamerecordings") for u in self.userdata_dirs()]
        roots += [_expand(p) for p in self.settings.get("extra_recording_dirs", []) if p]
        seen, out = set(), []
        for r in roots:
            rp = os.path.realpath(r)
            if rp not in seen and os.path.isdir(rp):
                seen.add(rp)
                out.append(rp)
        return out

    def scan(self):
        items = {}

        for ud in self.userdata_dirs():
            base = os.path.join(ud, "760", "remote")
            if not os.path.isdir(base):
                continue
            for appid in os.listdir(base):
                sdir = os.path.join(base, appid, "screenshots")
                if not os.path.isdir(sdir):
                    continue
                for f in os.listdir(sdir):
                    path = os.path.join(sdir, f)
                    if not f.lower().endswith(IMG_EXT) or not os.path.isfile(path):
                        continue
                    st = os.stat(path)
                    thumb = os.path.join(sdir, "thumbnails", f)
                    iid = _stable_id(path)
                    items[iid] = {
                        "id": iid, "kind": "screenshot",
                        "appid": int(appid) if appid.isdigit() else 0,
                        "mtime": st.st_mtime, "size": st.st_size, "duration": None,
                        "_path": path, "_thumb": thumb if os.path.isfile(thumb) else path,
                    }

        # Recordings: every folder with session.mpd. Sessions inside clip_* form one video.
        groups = {}
        for root in self.recording_roots():
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                if "session.mpd" not in filenames:
                    continue
                owner, cur = dirpath, dirpath
                while cur.startswith(root) and cur != root:
                    if os.path.basename(cur).startswith("clip_"):
                        owner = cur
                        break
                    cur = os.path.dirname(cur)
                groups.setdefault(owner, []).append(dirpath)

        for owner, sessions in groups.items():
            sessions.sort()
            m = CLIP_RE.search(os.path.basename(owner)) or CLIP_RE.search(os.path.basename(sessions[0]))
            appid = int(m.group(1)) if m else 0
            mtime = os.path.getmtime(owner)
            if m:
                try:
                    d, t = m.group(2), m.group(3)
                    mtime = time.mktime((int(d[:4]), int(d[4:6]), int(d[6:]),
                                         int(t[:2]), int(t[2:4]), int(t[4:]), 0, 0, -1))
                except (ValueError, OverflowError):
                    pass
            duration, size = 0.0, 0
            for s in sessions:
                d = _session_info(s)["duration"]
                duration += d or 0
                try:
                    size += sum(e.stat().st_size for e in os.scandir(s) if e.is_file())
                except OSError:
                    pass
            iid = _stable_id(owner)
            items[iid] = {
                "id": iid, "kind": "video", "appid": appid, "mtime": mtime, "size": size,
                "duration": duration or None, "_path": owner, "_sessions": sessions,
                "_kind_label": "clip" if os.path.basename(owner).startswith("clip_") else "recording",
            }

        with self.lock:
            self.index = items
        return [self.public_item(i) for i in sorted(items.values(), key=lambda x: -x["mtime"])]

    def exported_path(self, item):
        p = self.state["exported"].get(item["_path"])
        return p if p and os.path.isfile(p) else None

    def copies(self, item):
        """The plugin's own files for this item that take extra space: the
        exported MP4 and the outgoing copy in the Syncthing folder. A screenshot's
        outgoing copy is usually a hardlink of the Steam file (no extra space), so
        it only counts when it is a real separate copy."""
        out = []
        mp4 = self.exported_path(item)
        if mp4:
            out.append(mp4)
        sent = self.state["sent"].get(item["_path"])
        if sent and os.path.isfile(sent):
            if item["kind"] == "video":
                out.append(sent)
            else:
                try:
                    if not os.path.samefile(sent, item["_path"]):
                        out.append(sent)
                except OSError:
                    out.append(sent)
        return out

    def public_item(self, it):
        out = {k: v for k, v in it.items() if not k.startswith("_")}
        out["exported"] = it["kind"] == "video" and self.exported_path(it) is not None
        out["clip"] = it.get("_kind_label") == "clip"
        out["copies"] = bool(self.copies(it))
        return out

    def public_items(self, items):
        return [self.public_item(it) for it in items]

    # ---------- thumbnails

    def video_thumb(self, item):
        ff = _find_ffmpeg()
        out = os.path.join(THUMB_DIR, item["id"] + ".jpg")
        if os.path.isfile(out):
            return out
        for f in ("thumbnail.jpg", "thumb.jpg"):
            p = os.path.join(item["_path"], f)
            if os.path.isfile(p):
                return p
        if not ff:
            return None
        with self.thumb_lock:
            if os.path.isfile(out):
                return out
            os.makedirs(THUMB_DIR, exist_ok=True)
            session = item["_sessions"][0]
            info = _session_info(session)
            if info["video"] is None:
                return None
            tmp = os.path.join(THUMB_DIR, item["id"] + ".tmp.mp4")
            try:
                _concat_stream(session, info["video"], tmp, limit=1)
                subprocess.run(
                    [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", tmp,
                     "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "5", out],
                    env=_clean_env(), timeout=30, check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                decky.logger.warning(f"thumb failed for {item['_path']}: {e}")
                return None
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        return out if os.path.isfile(out) else None

    # ---------- export

    def export_video(self, item, name, set_stage):
        existing = self.exported_path(item)
        if existing:
            return existing
        ff = _find_ffmpeg()
        if not ff:
            raise UserError(T("ffmpeg_missing"))
        export_dir = _expand(self.settings["export_dir"])
        os.makedirs(export_dir, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(item["mtime"]))
        dest = _unique_path(os.path.join(export_dir, f"{_safe_name(name)}_{stamp}.mp4"))
        tmpdir = os.path.join(export_dir, f".dmg_tmp_{_new_id(4)}")
        os.makedirs(tmpdir)
        env = _clean_env()
        try:
            parts, hevc = [], False
            sessions = item["_sessions"]
            for i, session in enumerate(sessions):
                set_stage(T("stage_concat", i=i + 1, n=len(sessions)))
                info = _session_info(session)
                hevc = hevc or info["hevc"]
                inputs = []
                for sid in info["streams"]:
                    p = os.path.join(tmpdir, f"s{i}_{sid}.mp4")
                    _concat_stream(session, sid, p)
                    inputs.append(p)
                if not inputs:
                    continue
                set_stage(T("stage_mux", i=i + 1, n=len(sessions)))
                part = os.path.join(tmpdir, f"part{i}.mp4")
                cmd = [ff, "-hide_banner", "-loglevel", "error", "-y"]
                for p in inputs:
                    cmd += ["-i", p]
                for n in range(len(inputs)):
                    cmd += ["-map", str(n)]
                cmd += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
                if info["hevc"]:
                    cmd += ["-tag:v", "hvc1"]  # otherwise iPhones refuse HEVC
                cmd += ["-movflags", "+faststart", part]
                r = subprocess.run(cmd, env=env, capture_output=True, text=True)
                if r.returncode != 0:
                    raise UserError(T("ffmpeg_failed", err=(r.stderr.strip().splitlines() or ["?"])[-1]))
                parts.append(part)

            if not parts:
                raise UserError(T("no_data"))
            tmp_out = dest + ".part"
            if len(parts) == 1:
                os.replace(parts[0], tmp_out)
            else:
                set_stage(T("stage_merge"))
                lst = os.path.join(tmpdir, "list.txt")
                with open(lst, "w", encoding="utf-8") as f:
                    for p in parts:
                        f.write("file '" + p.replace("'", "'\\''") + "'\n")
                cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                       "-i", lst, "-c", "copy"]
                if hevc:
                    cmd += ["-tag:v", "hvc1"]
                cmd += ["-movflags", "+faststart", "-f", "mp4", tmp_out]
                r = subprocess.run(cmd, env=env, capture_output=True, text=True)
                if r.returncode != 0:
                    raise UserError(T("ffmpeg_failed", err=(r.stderr.strip().splitlines() or ["?"])[-1]))
            os.replace(tmp_out, dest)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.state["exported"][item["_path"]] = dest
        _save_json(STATE_PATH, self.state)
        return dest

    def delete_mp4(self, item):
        """Deletes only the exported MP4 (after a LocalSend transfer). Returns True if
        a file was removed."""
        mp4 = self.state["exported"].pop(item["_path"], None)
        removed = False
        if mp4:
            try:
                os.remove(mp4)
                removed = True
            except FileNotFoundError:
                pass
            _save_json(STATE_PATH, self.state)
        return removed

    def delete_local(self, item, set_stage):
        """Removes the plugin's copies of an item (exported MP4 and the outgoing
        Syncthing copy). Steam originals are never touched."""
        if not self.copies(item):
            raise UserError(T("nothing_to_delete"))
        self.retire_copy(item["_path"], set_stage)
        set_stage(T("stage_delete"))
        self.delete_mp4(item)
        return True

    # ---------- Syncthing: sending and removing copies

    def st_status(self):
        return _syncthing_status(self.settings["outbox_dir"])

    def _ignored_names(self, folder_root):
        """Paths excluded by this plugin in the folder's .stignore: a new copy must
        never get one of these names, or Syncthing would never send it."""
        out = set(self.state["retired"])
        try:
            with open(os.path.join(folder_root, ".stignore"), "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("/") and not line.startswith("//"):
                        rel = re.sub(r"\\(.)", r"\1", line[1:])
                        out.add(os.path.join(folder_root, rel))
        except OSError:
            pass
        return out

    def syncthing_send(self, item, name, set_stage):
        """Places a copy of the item into the Syncthing folder. Returns False if the
        current copy is still there (nothing to do)."""
        key = item["_path"]
        current = self.state["sent"].get(key)
        if current and os.path.isfile(current):
            return False
        src = item["_path"] if item["kind"] == "screenshot" else self.export_video(item, name, set_stage)
        set_stage(T("stage_outbox"))
        outbox = _expand(self.settings["outbox_dir"])
        folder = os.path.join(outbox, _safe_name(name)) if self.settings.get("per_game_folders") else outbox
        if item["kind"] == "screenshot":
            fname = f"{_safe_name(name)}_{os.path.basename(src)}"
        else:
            fname = os.path.basename(src)
        taken = self._ignored_names(outbox)
        base, ext = os.path.splitext(os.path.join(folder, fname))
        dest, i = base + ext, 2
        while os.path.lexists(dest) or dest in taken:
            dest = f"{base}_{i}{ext}"
            i += 1
        _link_or_copy(src, dest)
        self.state["sent"][key] = dest
        self.state["offloaded"].pop(key, None)
        known = self.state["paths"].setdefault(key, [])
        if dest not in known:
            known.append(dest)
        _save_json(STATE_PATH, self.state)
        return True

    def retire_copy(self, key, set_stage):
        """Hides the outgoing copy from Syncthing, then deletes it from this device.
        Deleting an ignored file is not propagated, so other devices keep it."""
        sent_copy = self.state["sent"].get(key)
        if not sent_copy or not os.path.lexists(sent_copy):
            self.state["sent"].pop(key, None)
            return
        set_stage(T("stage_hide"))
        st = self.st_status()
        root = st.get("_folder_root")
        if not st.get("running") or not root:
            raise UserError(T("st_down_delete"))
        real = os.path.realpath(sent_copy)
        if not real.startswith(root.rstrip("/") + "/"):
            raise UserError(T("outside_folder"))
        _st_protect(st, os.path.relpath(real, root))
        os.remove(sent_copy)
        self.state["offloaded"][key] = sent_copy
        self.state["sent"].pop(key, None)
        if sent_copy not in self.state["retired"]:
            self.state["retired"].append(sent_copy)
        _save_json(STATE_PATH, self.state)

    def auto_candidates(self):
        """Items sent via Syncthing that another device already has in full:
        their copies are safe to remove here."""
        if not (self.settings.get("auto_delete") and self.settings.get("syncthing_enabled")):
            return []
        if not self.state["sent"]:
            return []
        st = self.st_status()
        root = st.get("_folder_root")
        if not st.get("running") or not root:
            return []
        try:
            my_id = _st_my_id(st)
        except Exception as e:
            decky.logger.warning(f"auto-delete: {e}")
            return []
        with self.lock:
            empty = not self.index
        if empty:
            self.scan()
        with self.lock:
            by_path = {it["_path"]: it for it in self.index.values()}
        out = []
        for key, copy in list(self.state["sent"].items()):
            item = by_path.get(key)
            if not item or item["id"] in self.pending_delete or not os.path.exists(copy):
                continue
            if not self.copies(item):
                continue  # e.g. a hardlinked screenshot: removing it frees no space
            real = os.path.realpath(copy)
            if not real.startswith(root.rstrip("/") + "/"):
                continue
            try:
                if _st_on_remote(st, os.path.relpath(real, root), my_id):
                    out.append(item)
            except Exception as e:
                decky.logger.warning(f"auto-delete check failed: {e}")
                break
        return out

    def rescan_syncthing(self):
        st = self.st_status()
        if st.get("running") and st.get("folder_id"):
            try:
                _st_call(st, "POST", "/rest/db/scan?folder=" + _q(st["folder_id"]))
            except Exception as e:
                decky.logger.warning(f"syncthing rescan failed: {e}")

    # ---------- LocalSend: identity

    def alias(self):
        name = ""
        try:
            name = socket.gethostname()
        except OSError:
            pass
        return name or "Steam Deck"

    def my_info(self, announce=None):
        info = {
            "alias": self.alias(), "version": "2.1", "deviceModel": "Linux", "deviceType": "desktop",
            "fingerprint": self.settings["ls_fingerprint"], "port": LS_PORT, "protocol": "http",
            "download": False,
        }
        if announce is not None:
            info["announce"] = announce
            info["announcement"] = announce  # protocol v1 name
        return info

    # ---------- LocalSend: discovery

    def _remember_seen(self, dev):
        dev = dict(dev, seen=time.time())
        with self.seen_lock:
            self.seen[dev["fingerprint"]] = dev
        return dev

    def _on_packet(self, data, ip):
        try:
            msg = json.loads(data.decode("utf-8", "replace"))
        except ValueError:
            return
        if not isinstance(msg, dict):
            return
        fp = msg.get("fingerprint")
        if not fp or fp == self.settings["ls_fingerprint"]:
            return
        proto = msg.get("protocol") if msg.get("protocol") in ("http", "https") else "https"
        try:
            port = int(msg.get("port") or LS_PORT)
        except (TypeError, ValueError):
            port = LS_PORT
        # No reply to announcements: this device only sends, so it should not
        # appear as a target in other devices' LocalSend apps.
        self._remember_seen({
            "fingerprint": fp, "alias": str(msg.get("alias") or ip), "ip": ip, "port": port,
            "protocol": proto, "deviceType": msg.get("deviceType") or "", "deviceModel": msg.get("deviceModel") or "",
        })

    def _send_multicast(self, info):
        payload = json.dumps(info).encode("utf-8")
        ips = [ip for ip, _ in _local_ipv4()] or [None]
        for ip in ips:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            try:
                s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
                if ip:
                    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ip))
                s.sendto(payload, (LS_GROUP, LS_PORT))
            except OSError:
                pass
            finally:
                s.close()

    def _multicast_socket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        s.bind(("", LS_PORT))
        group = socket.inet_aton(LS_GROUP)
        joined = False
        for ip, _ in _local_ipv4():
            try:
                s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, group + socket.inet_aton(ip))
                joined = True
            except OSError:
                pass
        if not joined:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, group + socket.inet_aton("0.0.0.0"))
        s.settimeout(1.0)
        return s

    def listen_loop(self):
        """Collects LocalSend announcements. The socket is recreated every minute,
        so the plugin follows network changes (Wi-Fi reconnects, hotspots)."""
        while not self.stop.is_set():
            try:
                s = self._multicast_socket()
            except OSError as e:
                decky.logger.warning(f"LocalSend multicast unavailable: {e}")
                self.stop.wait(15)
                continue
            started = time.time()
            try:
                while not self.stop.is_set() and time.time() - started < 60:
                    try:
                        data, addr = s.recvfrom(65535)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    self._on_packet(data, addr[0])
            finally:
                s.close()

    def probe(self, host, port=LS_PORT):
        """Asks a host directly whether it runs LocalSend (HTTPS first, then HTTP)."""
        for proto in ("https", "http"):
            base = f"{proto}://{_host(host)}:{port}{LS_API}"
            status, data, _ = _curl_json("POST", base + "/register", self.my_info(), timeout=6, connect_timeout=3)
            if status != 200 or not isinstance(data, dict):
                status, data, _ = _curl_json("GET", base + "/info", timeout=6, connect_timeout=3)
            if status == 200 and isinstance(data, dict) and data.get("fingerprint"):
                if data["fingerprint"] == self.settings["ls_fingerprint"]:
                    return None
                return self._remember_seen({
                    "fingerprint": data["fingerprint"], "alias": str(data.get("alias") or host), "ip": host,
                    "port": port, "protocol": proto, "deviceType": data.get("deviceType") or "",
                    "deviceModel": data.get("deviceModel") or "",
                })
        return None

    def _scan_subnets(self):
        """Looks for an open LocalSend port on the local /24 networks, for networks
        where multicast is filtered (phone hotspots, some routers)."""
        local = _local_ipv4()
        own = {ip for ip, _ in local}
        hosts = []
        for ip, prefix in local:
            if prefix < 16 or prefix >= 31:
                continue  # skip point-to-point links such as VPN tunnels
            base = ip.rsplit(".", 1)[0]
            hosts += [f"{base}.{i}" for i in range(1, 255) if f"{base}.{i}" not in own]
        for g in _gateways():
            if g not in hosts and g not in own:
                hosts.append(g)
        open_hosts, guard = [], threading.Semaphore(64)

        def check(h):
            with guard:
                try:
                    socket.create_connection((h, LS_PORT), timeout=0.6).close()
                    open_hosts.append(h)
                except OSError:
                    pass

        threads = [threading.Thread(target=check, args=(h,), daemon=True) for h in hosts]
        for t in threads:
            t.start()
        for t in threads:
            t.join(3)
        probes = [threading.Thread(target=self.probe, args=(h,), daemon=True) for h in open_hosts]
        for t in probes:
            t.start()
        for t in probes:
            t.join(6)

    def discover(self, wait=3.0):
        """Announces this device, scans the network and checks saved devices.
        Returns the devices found, saved ones first."""
        start = time.time()
        self._send_multicast(self.my_info(announce=True))
        workers = [threading.Thread(target=self._scan_subnets, daemon=True)]
        for d in self.settings.get("ls_known", []):
            workers.append(threading.Thread(target=self.probe, args=(d["ip"], d.get("port") or LS_PORT), daemon=True))
        for t in workers:
            t.start()
        deadline = start + max(wait, 1.0) + 8
        for t in workers:
            t.join(max(0.1, deadline - time.time()))
        remaining = start + wait - time.time()
        if remaining > 0:
            time.sleep(remaining)
        with self.seen_lock:
            found = [d for d in self.seen.values() if d["seen"] >= start - 1]
        return self.describe(found)

    def describe(self, devices):
        known = {d["fingerprint"]: d for d in self.settings.get("ls_known", [])}
        last = self.settings.get("ls_last")
        out = []
        for d in devices:
            item = {k: d.get(k) for k in ("fingerprint", "alias", "ip", "port", "protocol", "deviceType", "deviceModel")}
            item["known"] = d["fingerprint"] in known
            item["last"] = d["fingerprint"] == last
            out.append(item)
        out.sort(key=lambda d: (not d["last"], not d["known"], (d["alias"] or "").lower()))
        return out

    def remember_device(self, dev):
        known = [d for d in self.settings.get("ls_known", []) if d.get("fingerprint") != dev["fingerprint"]]
        known.insert(0, {k: dev.get(k) for k in ("fingerprint", "alias", "ip", "port", "protocol", "deviceType",
                                                  "deviceModel")})
        self.settings["ls_known"] = known[:20]
        self.settings["ls_last"] = dev["fingerprint"]
        self.save_settings()

    def forget_device(self, fingerprint):
        self.settings["ls_known"] = [d for d in self.settings.get("ls_known", []) if d.get("fingerprint") != fingerprint]
        if self.settings.get("ls_last") == fingerprint:
            self.settings["ls_last"] = ""
        self.save_settings()

    def add_device(self, host):
        host = (host or "").strip()
        port = LS_PORT
        m = re.fullmatch(r"(\d+\.\d+\.\d+\.\d+):(\d+)", host)
        if m:
            host, port = m.group(1), int(m.group(2))
        dev = self.probe(host, port) if host else None
        if not dev:
            raise UserError(T("ls_not_found", host=host or "?"))
        self.remember_device(dev)
        return self.describe([dev])[0]

    # ---------- LocalSend: sending

    def _target(self, target):
        """Uses the most recent address of the device if it changed since it was picked."""
        with self.seen_lock:
            fresh = self.seen.get(target.get("fingerprint"))
        if fresh and time.time() - fresh["seen"] < 300:
            return dict(target, ip=fresh["ip"], port=fresh["port"], protocol=fresh["protocol"])
        return target

    def _upload(self, url, path, progress, alias):
        cmd = ["curl", "-k", *CLIENT_CERT["args"], "-#", "--connect-timeout", "10", "-X", "POST", "-T", path,
               "-H", "Content-Type: application/octet-stream", "-H", "Expect:",
               "-o", "/dev/null", "-w", "%{http_code}", url]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_clean_env())
        pending, errors, last = b"", b"", -1
        fd = proc.stderr.fileno()
        while True:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            errors = (errors + chunk)[-2000:]
            # curl -# redraws its progress bar ending with " NN.N%" after each \r
            lines = re.split(rb"[\r\n]", pending + chunk)
            pending = lines.pop()[-200:]
            for line in lines:
                m = re.search(rb"(\d{1,3}(?:[.,]\d)?)%\s*$", line)
                if m:
                    pct = min(100, int(float(m.group(1).replace(b",", b"."))))
                    if pct > last:
                        last = pct
                        progress(pct / 100.0)
        proc.wait()
        code = (proc.stdout.read() or b"").decode().strip()
        if proc.returncode == 0 and code.isdigit() and code != "200":
            raise UserError(T("ls_error", name=alias, code=code))
        if proc.returncode != 0 or code != "200":
            text = errors.decode("utf-8", "replace")
            lines = [ln for ln in re.split(r"[\r\n]", text) if ln.strip() and "#" not in ln]
            raise UserError(T("ls_failed", err=(lines[-1] if lines else f"HTTP {code or '?'}")))

    def send_files(self, items, names, target, pin, set_stage):
        if target.get("kind") == "syncthing":
            return self.send_syncthing(items, names, set_stage)
        return self.send_localsend(items, names, target, pin, set_stage)

    def send_syncthing(self, items, names, set_stage):
        if not self.settings.get("syncthing_enabled"):
            raise UserError(T("st_disabled"))
        st = self.st_status()
        if not (st.get("running") and st.get("outbox_shared")):
            raise UserError(T("st_unavailable", msg=st["message"]))
        n, count = len(items), 0
        for i, item in enumerate(items):
            name = names[i] if i < len(names) else "Steam"

            def stage(text, i=i):
                set_stage(f"{text} · {i + 1}/{n}" if n > 1 else text)
            if self.syncthing_send(item, name, stage):
                count += 1
        self.rescan_syncthing()
        return {"device": st.get("folder_label") or "Syncthing", "via": "syncthing", "count": count,
                "already": n - count, "exported": [it["id"] for it in items if it["kind"] == "video"],
                "deleted": [], "items": self.public_items(items)}

    def send_localsend(self, items, names, target, pin, set_stage):
        target = self._target(target)
        alias = target.get("alias") or target.get("ip")
        entries, n = [], len(items)
        for i, item in enumerate(items):
            name = names[i] if i < len(names) else "Steam"
            if item["kind"] == "video":
                def stage(text, i=i):
                    set_stage(f"{text} · {i + 1}/{n}" if n > 1 else text)
                path = self.export_video(item, name, stage)
                fname = os.path.basename(path)
            else:
                path = item["_path"]
                fname = f"{_safe_name(name)}_{os.path.basename(path)}"
            entries.append({"id": _new_id(6), "path": path, "name": fname, "size": os.path.getsize(path),
                            "mime": _mime(path), "item": item})

        base = f"{target['protocol']}://{_host(target['ip'])}:{target.get('port') or LS_PORT}{LS_API}"
        body = {"info": self.my_info(), "files": {
            e["id"]: {"id": e["id"], "fileName": e["name"], "size": e["size"], "fileType": e["mime"],
                      "sha256": None, "preview": None} for e in entries}}
        set_stage(T("stage_waiting", name=alias))
        query = f"?pin={_q(pin)}" if pin else ""
        status, data, err = _curl_json("POST", base + "/prepare-upload" + query, body, timeout=300, connect_timeout=6)
        decky.logger.info(f"prepare-upload {base}: HTTP {status} {err}")
        if status == 0:
            if err == "timeout" or "timed out" in err:
                raise UserError(T("ls_no_response", name=alias))
            if re.search(r"SSL|TLS|certificate", err, re.I):
                raise UserError(T("ls_tls", name=alias, err=err))
            raise UserError(T("ls_unreachable", name=alias))
        if status == 204:
            tokens = {}
        elif status == 200 and isinstance(data, dict):
            tokens = data.get("files") or {}
        else:
            raise UserError({401: T("ls_pin", name=alias), 403: T("ls_rejected", name=alias),
                             409: T("ls_busy", name=alias), 429: T("ls_too_many")}.get(
                status, T("ls_error", name=alias, code=status)))
        session = data.get("sessionId", "") if isinstance(data, dict) else ""

        wanted = [e for e in entries if e["id"] in tokens]
        total = sum(e["size"] for e in wanted) or 1
        done = 0
        try:
            for e in wanted:
                url = (f"{base}/upload?sessionId={_q(session)}&fileId={_q(e['id'])}"
                       f"&token={_q(tokens[e['id']])}")
                self._upload(url, e["path"], lambda frac, e=e, done=done: set_stage(
                    T("stage_sending", pct=min(100, int((done + frac * e["size"]) * 100 / total)))), alias)
                done += e["size"]
        except Exception:
            if session:
                _curl_json("POST", f"{base}/cancel?sessionId={_q(session)}", timeout=5, connect_timeout=3)
            raise

        self.remember_device(target)
        exported = [e["item"]["id"] for e in entries if e["item"]["kind"] == "video"]
        deleted = []
        if self.settings.get("auto_delete"):
            sent_ids = {e["item"]["id"] for e in wanted}
            for e in entries:
                if e["item"]["kind"] == "video" and e["item"]["id"] in sent_ids and self.delete_mp4(e["item"]):
                    deleted.append(e["item"]["id"])
        return {"device": alias, "via": "localsend", "count": len(wanted), "exported": exported,
                "deleted": deleted, "items": self.public_items(items)}

    # ---------- installing ffmpeg / Syncthing

    def install(self, component, set_stage):
        spec = BINARIES.get(component)
        if not spec:
            raise UserError(T("unknown_component"))
        if component == "syncthing":
            st = self.st_status()
            if st["found"] and not st["managed"]:
                raise UserError(T("st_other_exists"))
        env = _clean_env()
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(BIN_DIR, exist_ok=True)
        archive = os.path.join(DOWNLOAD_DIR, os.path.basename(spec["url"]))
        part = archive + ".part"
        target = os.path.join(BIN_DIR, component)
        try:
            # download with curl, reporting progress by watching the file size
            if os.path.exists(part):
                os.remove(part)
            set_stage(T("stage_download", pct=0))
            proc = subprocess.Popen(
                ["curl", "-fL", "--retry", "3", "--connect-timeout", "20", "-sS", "-o", part, spec["url"]],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            last = -1
            while proc.poll() is None:
                time.sleep(0.5)
                try:
                    pct = min(99, int(os.path.getsize(part) * 100 / spec["size"]))
                except OSError:
                    pct = 0
                if pct != last:
                    set_stage(T("stage_download", pct=pct))
                    last = pct
            if proc.returncode != 0:
                err = (proc.stderr.read() if proc.stderr else "").strip().splitlines()
                raise UserError(T("download_failed", err=(err or [f"curl {proc.returncode}"])[-1]))

            set_stage(T("stage_verify"))
            r = subprocess.run(["sha256sum", part], env=env, capture_output=True, text=True)
            if r.returncode != 0 or r.stdout.split()[0].lower() != spec["sha256"]:
                raise UserError(T("bad_checksum"))
            os.replace(part, archive)

            set_stage(T("stage_unpack"))
            tmp_target = target + ".new"
            if spec["format"] == "gz":
                with open(tmp_target, "wb") as out:
                    r = subprocess.run(["gzip", "-dc", archive], env=env, stdout=out, stderr=subprocess.PIPE)
                if r.returncode != 0:
                    raise UserError(T("binary_broken"))
            else:
                unpack = os.path.join(DOWNLOAD_DIR, "unpack")
                shutil.rmtree(unpack, ignore_errors=True)
                os.makedirs(unpack)
                r = subprocess.run(["tar", "-xzf", archive, "-C", unpack, spec["member"]],
                                   env=env, capture_output=True, text=True)
                if r.returncode != 0:
                    raise UserError(T("binary_broken"))
                shutil.move(os.path.join(unpack, spec["member"]), tmp_target)
                shutil.rmtree(unpack, ignore_errors=True)
            os.chmod(tmp_target, 0o755)
            check = subprocess.run([tmp_target, "-version" if component == "ffmpeg" else "--version"],
                                   env=env, capture_output=True, text=True, timeout=30)
            if check.returncode != 0:
                raise UserError(T("binary_broken"))
            os.replace(tmp_target, target)
        finally:
            for p in (part, archive, target + ".new"):
                try:
                    os.remove(p)
                except FileNotFoundError:
                    pass

        if component == "syncthing":
            set_stage(T("stage_start"))
            if not self.settings.get("st_key"):
                self.settings["st_key"] = _new_id(16)
            if not self.settings.get("st_port") or not self.settings.get("st_managed"):
                self.settings["st_port"] = next((p for p in range(8384, 8400) if _port_free(p)), 8384)
            self.settings["st_managed"] = True
            self.save_settings()
            self.start_syncthing(wait=True)
        return target

    def start_syncthing(self, wait=False):
        """Starts the plugin's own Syncthing if it is not running already."""
        managed = _managed()
        binary = _own_binary("syncthing")
        if not managed or not binary:
            return False
        log = os.path.join(ST_HOME, "syncthing.log")
        with self.st_lock:
            if _ping(managed["base"], managed["key"]):
                return True
            os.makedirs(ST_HOME, exist_ok=True)
            env = _clean_env()
            env["STNODEFAULTFOLDER"] = "1"  # no default "Sync" folder in the home dir
            subprocess.Popen(
                [binary, "serve", f"--home={ST_HOME}", "--no-browser", "--no-upgrade",
                 f"--gui-address=http://127.0.0.1:{self.settings['st_port']}",
                 f"--gui-apikey={self.settings['st_key']}",
                 f"--log-file={log}", "--log-max-size=1048576", "--log-max-old-files=1"],
                env=env, cwd=ST_HOME, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True)
            if not wait:
                return True
            deadline = time.time() + 45
            while time.time() < deadline:
                if _ping(managed["base"], managed["key"]):
                    return True
                time.sleep(1)
        raise UserError(T("st_start_failed", log=log))

    def stop_syncthing(self):
        managed = _managed()
        if managed and _ping(managed["base"], managed["key"]):
            try:
                _http(managed["base"], "POST", "/rest/system/shutdown", {"X-API-Key": managed["key"]})
            except Exception:
                pass


    # ---------- setup screen, pairing Syncthing devices

    def setup_info(self):
        ff = _find_ffmpeg()
        info = {
            "ffmpeg": ff,
            "ffmpeg_own": bool(ff) and ff == _own_binary("ffmpeg"),
            "alias": self.alias(),
            "known": self.describe(self.settings.get("ls_known", [])),
            "gateways": _gateways(),
            "addresses": [ip for ip, _ in _local_ipv4()],
            "syncthing_enabled": bool(self.settings.get("syncthing_enabled")),
            "syncthing": None,
            "st_installed": bool(_own_binary("syncthing")),
            "outbox": _expand(self.settings["outbox_dir"]),
            "my_id": None,
            "devices": [],
            "pending": [],
        }
        if not info["syncthing_enabled"]:
            return info
        st = self.st_status()
        info["syncthing"] = _public(st)
        if not st.get("running"):
            return info
        try:
            info["my_id"] = _st_my_id(st)
            devices = _st_ok(st, "GET", "/rest/config/devices") or []
            conns = (_st_ok(st, "GET", "/rest/system/connections") or {}).get("connections") or {}
            shared = set()
            if st.get("folder_id"):
                folder = _st_ok(st, "GET", "/rest/config/folders/" + _q(st["folder_id"])) or {}
                shared = {d.get("deviceID") for d in folder.get("devices") or []}
            for d in devices:
                did = d.get("deviceID")
                if not did or did == info["my_id"]:
                    continue
                info["devices"].append({
                    "id": did, "name": d.get("name") or did[:7],
                    "connected": bool((conns.get(did) or {}).get("connected")),
                    "shared": did in shared,
                })
            pending = _st_ok(st, "GET", "/rest/cluster/pending/devices") or {}
            known = {d["id"] for d in info["devices"]}
            for did, p in pending.items():
                if did not in known:
                    info["pending"].append({"id": did, "name": (p or {}).get("name") or did[:7]})
        except Exception as e:
            decky.logger.warning(f"setup_info: {e}")
        return info

    def connect_device(self, device_id, name):
        """Adds a device (if new) and shares the send folder with it,
        creating the folder in Syncthing when needed."""
        outbox = _expand(self.settings["outbox_dir"])
        st = self.st_status()
        if not st.get("running"):
            raise UserError(T("st_not_running"))
        my_id = _st_my_id(st)
        status, _ = _st_call(st, "GET", "/rest/config/devices/" + _q(device_id))
        if status == 404:
            dev = _st_ok(st, "GET", "/rest/config/defaults/device") or {}
            dev.update(deviceID=device_id, name=name or device_id[:7])
            _st_ok(st, "POST", "/rest/config/devices", dev)
        elif status >= 300:
            raise UserError(T("st_api", code=status))

        if st.get("folder_id"):
            path = "/rest/config/folders/" + _q(st["folder_id"])
            folder = _st_ok(st, "GET", path) or {}
            devs = folder.get("devices") or []
            if device_id not in {d.get("deviceID") for d in devs}:
                devs.append({"deviceID": device_id})
                folder["devices"] = devs
                _st_ok(st, "PUT", path, folder)
        else:
            os.makedirs(outbox, exist_ok=True)
            folder = _st_ok(st, "GET", "/rest/config/defaults/folder") or {}
            folder.update(
                id="deck-media-" + _new_id(3), label=FOLDER_LABEL, path=outbox,
                type="sendonly", devices=[{"deviceID": my_id}, {"deviceID": device_id}])
            _st_ok(st, "POST", "/rest/config/folders", folder)
        return True


    # ---------- http (asyncio, no http.server)

    def resolve(self, route, item_id):
        with self.lock:
            item = self.index.get(item_id)
        if not item:
            return None
        if route == "/thumb":
            return item["_thumb"] if item["kind"] == "screenshot" else self.video_thumb(item)
        if route == "/file":
            return item["_path"] if item["kind"] == "screenshot" else self.exported_path(item)
        return None

    async def handle_http(self, reader, writer):
        loop = asyncio.get_running_loop()
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
            lines = head.decode("latin-1").split("\r\n")
            parts = lines[0].split(" ")
            if len(parts) < 2 or parts[0] not in ("GET", "HEAD"):
                return await self.http_error(writer, 405)
            headers = {}
            for line in lines[1:]:
                k, sep, v = line.partition(":")
                if sep:
                    headers[k.strip().lower()] = v.strip()
            route, _, query = parts[1].partition("?")
            q = {}
            for pair in query.split("&"):
                k, _, v = pair.partition("=")
                q[k] = v
            if q.get("t") != self.token:
                return await self.http_error(writer, 403)
            path = await loop.run_in_executor(None, self.resolve, route, q.get("id", ""))
            if not path or not os.path.isfile(path):
                return await self.http_error(writer, 404)

            size = os.path.getsize(path)
            ctype = _mime(path)
            start, end = 0, size - 1
            status = "200 OK"
            m = re.match(r"bytes=(\d*)-(\d*)", headers.get("range", ""))
            if m and size:
                if m.group(1):
                    start = int(m.group(1))
                    if m.group(2):
                        end = min(int(m.group(2)), size - 1)
                elif m.group(2):
                    start = max(0, size - int(m.group(2)))
                if start > end:
                    return await self.http_error(writer, 416)
                status = "206 Partial Content"
            hdr = [f"HTTP/1.1 {status}", f"Content-Type: {ctype}", "Accept-Ranges: bytes",
                   f"Content-Length: {end - start + 1}", "Cache-Control: max-age=3600",
                   "Access-Control-Allow-Origin: *", "Connection: close"]
            if status.startswith("206"):
                hdr.append(f"Content-Range: bytes {start}-{end}/{size}")
            writer.write(("\r\n".join(hdr) + "\r\n\r\n").encode())
            if parts[0] == "GET":
                with open(path, "rb") as f:
                    f.seek(start)
                    left = end - start + 1
                    while left > 0:
                        buf = await loop.run_in_executor(None, f.read, min(1 << 18, left))
                        if not buf:
                            break
                        writer.write(buf)
                        await writer.drain()
                        left -= len(buf)
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError, asyncio.TimeoutError):
            pass
        except Exception:
            decky.logger.exception("http handler failed")
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def http_error(self, writer, code):
        text = {403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed", 416: "Range Not Satisfiable"}[code]
        writer.write(f"HTTP/1.1 {code} {text}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())
        await writer.drain()

    async def start_http(self):
        self.server = await asyncio.start_server(self.handle_http, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    # ---------- jobs

    async def add_job(self, item_ids, action, auto=False, **extra):
        job = {"id": _new_id(5), "item_ids": list(item_ids), "item_id": (list(item_ids) or [""])[0],
               "action": action, "auto": auto, "status": "queued", "stage": "", "error": None, "result": None}
        if action == "delete":
            self.pending_delete.update(job["item_ids"])
        self.jobs[job["id"]] = dict(job, **extra)
        await self.queue.put(job["id"])
        await decky.emit("dmg_job", job)
        return job

    def _items(self, ids):
        with self.lock:
            items = [self.index.get(i) for i in ids]
        if not ids or any(i is None for i in items):
            raise UserError(T("not_found_refresh"))
        return items

    async def run_worker(self):
        loop = asyncio.get_running_loop()
        while True:
            job_id = await self.queue.get()
            full = self.jobs.get(job_id) or {}
            job = {k: full.get(k) for k in
                   ("id", "item_ids", "item_id", "action", "auto", "status", "stage", "error", "result")}
            job["status"] = "running"
            await decky.emit("dmg_job", dict(job))

            def set_stage(text, job=job):
                job["stage"] = text
                asyncio.run_coroutine_threadsafe(decky.emit("dmg_job", dict(job)), loop)

            try:
                action = job["action"]
                if action == "install":
                    job["result"] = await loop.run_in_executor(None, self.install, job["item_id"], set_stage)
                elif action == "send":
                    items = self._items(job["item_ids"])
                    job["result"] = await loop.run_in_executor(
                        None, self.send_files, items, full.get("names") or [], full["target"],
                        full.get("pin") or "", set_stage)
                elif action == "export":
                    item = self._items(job["item_ids"])[0]
                    await loop.run_in_executor(None, self.export_video, item, (full.get("names") or [""])[0],
                                               set_stage)
                    job["result"] = {"exported": [item["id"]], "items": self.public_items([item])}
                elif action == "delete":
                    item = self._items(job["item_ids"])[0]
                    await loop.run_in_executor(None, self.delete_local, item, set_stage)
                    job["result"] = {"deleted": [item["id"]], "items": self.public_items([item])}
                job["status"] = "done"
                job["stage"] = ""
            except UserError as e:
                job["status"] = "error"
                job["error"] = str(e)
            except Exception as e:
                decky.logger.exception("job failed")
                job["status"] = "error"
                job["error"] = str(e)
            self.jobs.pop(job_id, None)
            if job["action"] == "delete":
                self.pending_delete.difference_update(job["item_ids"] or [])
            await decky.emit("dmg_job", dict(job))
            self.queue.task_done()

    async def auto_loop(self):
        """Removes copies of files that another device has received via Syncthing."""
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(20)
            try:
                for item in await loop.run_in_executor(None, self.auto_candidates):
                    await self.add_job([item["id"]], "delete", auto=True)
            except Exception:
                decky.logger.exception("auto-delete loop")

    async def keep_syncthing(self):
        """Starts the plugin's Syncthing on load and restarts it if it stops."""
        loop = asyncio.get_running_loop()
        while True:
            try:
                if self.settings.get("syncthing_enabled") and _managed() and _own_binary("syncthing"):
                    await loop.run_in_executor(None, self.start_syncthing)
            except Exception:
                decky.logger.exception("syncthing watchdog")
            await asyncio.sleep(60)


try:
    _migrate_old_name()
except Exception:
    decky.logger.exception("taking over the settings of Deck Media Gallery failed")
core = Core()


class Plugin:
    async def set_language(self, code):
        LANG["code"] = "ru" if str(code).lower().startswith("ru") else "en"
        return LANG["code"]

    async def get_status(self):
        loop = asyncio.get_running_loop()
        settings = {k: v for k, v in core.settings.items() if not k.startswith("ls_") and k != "st_key"}
        known = core.settings.get("ls_known", [])
        last = next((d for d in known if d.get("fingerprint") == core.settings.get("ls_last")), None)
        st = None
        if core.settings.get("syncthing_enabled"):
            st = _public(await loop.run_in_executor(None, core.st_status))
        return {
            "port": core.port,
            "token": core.token,
            "ffmpeg": _find_ffmpeg(),
            "settings": settings,
            "alias": core.alias(),
            "last_device": last.get("alias") if last else None,
            "known_count": len(known),
            "syncthing": st,
        }

    async def list_media(self):
        return await asyncio.get_running_loop().run_in_executor(None, core.scan)

    async def enqueue(self, items, action):
        """Per-item jobs: "export" or "delete" (the plugin's copies)."""
        if action not in ("export", "delete"):
            return []
        return [await core.add_job([it.get("id")], action, names=[it.get("name") or "Steam"]) for it in items]

    async def send(self, items, target, pin=""):
        """target: a LocalSend device, or {"kind": "syncthing"}."""
        if not items or not isinstance(target, dict):
            return None
        if target.get("kind") != "syncthing" and not target.get("ip"):
            return None
        return await core.add_job([it.get("id") for it in items], "send",
                                  names=[it.get("name") or "Steam" for it in items], target=target, pin=pin)

    async def discover(self):
        return await asyncio.get_running_loop().run_in_executor(None, core.discover)

    async def add_device(self, host):
        loop = asyncio.get_running_loop()
        try:
            return {"ok": True, "device": await loop.run_in_executor(None, core.add_device, host)}
        except UserError as e:
            return {"ok": False, "error": str(e)}

    async def forget_device(self, fingerprint):
        core.forget_device(fingerprint)
        return True

    async def install(self, component):
        if component not in BINARIES:
            return None
        return await core.add_job([component], "install")

    async def setup_info(self):
        return await asyncio.get_running_loop().run_in_executor(None, core.setup_info)

    async def connect_device(self, device_id, name):
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, core.connect_device, device_id, name)
            return {"ok": True}
        except Exception as e:
            decky.logger.warning(f"connect_device: {e}")
            return {"ok": False, "error": str(e)}

    async def start_syncthing(self):
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, lambda: core.start_syncthing(wait=True))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def save_settings(self, settings):
        """Accepts the full settings object or only the changed keys."""
        settings = settings or {}
        for key in ("export_dir", "outbox_dir"):
            if isinstance(settings.get(key), str) and settings[key].strip():
                core.settings[key] = settings[key].strip()
        for key in ("auto_delete", "per_game_folders"):
            if key in settings:
                core.settings[key] = bool(settings[key])
        if "syncthing_enabled" in settings:
            enabled = bool(settings["syncthing_enabled"])
            was = bool(core.settings.get("syncthing_enabled"))
            core.settings["syncthing_enabled"] = enabled
            loop = asyncio.get_running_loop()
            if was and not enabled:
                await loop.run_in_executor(None, core.stop_syncthing)
            elif enabled and not was and _managed() and _own_binary("syncthing"):
                loop.run_in_executor(None, core.start_syncthing)
        if settings.get("ui_layout") in ("days", "grid"):
            core.settings["ui_layout"] = settings["ui_layout"]
        if "ui_tile" in settings:
            try:
                core.settings["ui_tile"] = max(120, min(400, int(settings["ui_tile"])))
            except (TypeError, ValueError):
                pass
        extra = settings.get("extra_recording_dirs")
        if isinstance(extra, list):
            core.settings["extra_recording_dirs"] = [e.strip() for e in extra if e and e.strip()]
        core.save_settings()
        return await self.get_status()

    async def _main(self):
        loop = asyncio.get_running_loop()
        core.queue = asyncio.Queue()
        try:
            await loop.run_in_executor(None, core.migrate)
        except Exception:
            decky.logger.exception("migration failed")
        await core.start_http()
        core.stop.clear()
        threading.Thread(target=core.listen_loop, daemon=True).start()
        core.tasks = [loop.create_task(core.run_worker()), loop.create_task(core.auto_loop()),
                      loop.create_task(core.keep_syncthing())]
        decky.logger.info(f"Deck Clip Export: http on 127.0.0.1:{core.port}")

    async def _unload(self):
        # The plugin's Syncthing keeps running on purpose: it lives in its own session.
        core.stop.set()
        for task in core.tasks:
            task.cancel()
        if core.server:
            core.server.close()

    async def _uninstall(self):
        core.stop.set()
        await asyncio.get_running_loop().run_in_executor(None, core.stop_syncthing)
        shutil.rmtree(THUMB_DIR, ignore_errors=True)
        shutil.rmtree(BIN_DIR, ignore_errors=True)
