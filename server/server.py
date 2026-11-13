"""PC Remote: explicit shared folder, pinned TLS and bearer authentication."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import socket
import ssl
import stat
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

API_VERSION = 1
CHUNK = 256 * 1024
MAX_UPLOAD = 1024 * 1024 * 1024


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def valid_name(name: str) -> str:
    # Apply Windows rules on every platform. Never permit ADS, device names or paths.
    if (not name or len(name) > 180 or name in (".", "..")
            or any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name)
            or name.endswith((" ", "."))
            or name.lower().startswith(".pcremote-")
            or re.fullmatch(r"con|prn|aux|nul|conin\$|conout\$|com[0-9¹²³]|lpt[0-9¹²³]",
                            name.partition(".")[0].rstrip(), re.IGNORECASE)):
        raise ApiError(400, "Недопустимое имя файла или папки.")
    return name


class Share:
    def __init__(self, root: Path, token: str, read_only: bool = False,
                 max_upload: int = MAX_UPLOAD):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Общая папка должна быть каталогом.")
        self.token = token
        self.read_only = read_only
        self.max_upload = max_upload
        self.mutation_lock = threading.Lock()
        self.auth_lock = threading.Lock()
        self.failures: dict[str, list[float]] = {}

    def authenticate(self, ip: str, authorization: str) -> None:
        now = time.monotonic()
        with self.auth_lock:
            self.failures = {key: [t for t in ts if now - t < 60]
                             for key, ts in self.failures.items()
                             if ts and now - ts[-1] < 60}
            recent = self.failures.get(ip, [])
            if len(recent) >= 12:
                raise ApiError(429, "Слишком много попыток. Подождите минуту.")
            supplied = authorization.removeprefix("Bearer ")
            if not authorization.startswith("Bearer ") or not hmac.compare_digest(
                    supplied.encode("utf-8"), self.token.encode("utf-8")):
                recent.append(now)
                self.failures[ip] = recent
                raise ApiError(401, "Неверный ключ доступа.")

    def path(self, relative: str) -> Path:
        if (len(relative) > 2048 or "\\" in relative or "\x00" in relative
                or relative.startswith("/") or ":" in relative):
            raise ApiError(403, "Путь вне общей папки запрещён.")
        parts = PurePosixPath(relative).parts
        if ".." in parts:
            raise ApiError(403, "Путь вне общей папки запрещён.")
        current = self.root
        for part in parts:
            valid_name(part)
            current = current / part
            # Do not follow symlinks, junctions or other Windows reparse points.
            if current.is_symlink() or (
                    current.exists()
                    and getattr(current.lstat(), "st_file_attributes", 0) & 0x400):
                raise ApiError(403, "Ссылки и точки подключения недоступны.")
        resolved = current.resolve()
        if not resolved.is_relative_to(self.root):
            raise ApiError(403, "Путь вне общей папки запрещён.")
        return resolved

    def writable(self) -> None:
        if self.read_only:
            raise ApiError(403, "Сервер работает только для чтения.")


class FileServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], share: Share,
                 tls: ssl.SSLContext | None = None):
        self.share = share
        self.tls = tls
        self.slots = threading.BoundedSemaphore(12)
        super().__init__(address, Handler)

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(30)
        return sock, address

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            if self.tls:
                request = self.tls.wrap_socket(request, server_side=True)
            super().process_request_thread(request, client_address)
        except (OSError, ssl.SSLError):
            request.close()
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    server: FileServer
    server_version = "PCRemote/1"
    sys_version = ""
    protocol_version = "HTTP/1.0"
    committed = False
    body_remaining = 0

    def log_message(self, format, *args):
        # Do not log paths, headers or secrets.
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.committed = True
        super().end_headers()

    def reply(self, status: int, value: dict):
        if self.committed:
            return
        # Closing a TLS socket with an unread request body may reset it on Windows,
        # discarding the error response. Drain small rejected bodies, never huge uploads.
        if status >= 400 and 0 < self.body_remaining <= 65536:
            self.connection.settimeout(2)
            try:
                self.read_body(self.body_remaining)
            except OSError:
                pass
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_body(self, count: int) -> bytes:
        data = self.rfile.read(count)
        self.body_remaining = max(0, self.body_remaining - len(data))
        return data

    def length(self, limit: int) -> int:
        if self.headers.get("Transfer-Encoding"):
            raise ApiError(400, "Нужна передача с Content-Length.")
        raw = self.headers.get("Content-Length", "")
        if len(raw) > 16 or not raw.isascii() or not raw.isdigit():
            raise ApiError(411, "Не указан размер данных.")
        size = int(raw)
        if size > limit:
            raise ApiError(413, "Превышен допустимый размер.")
        return size

    def json_body(self) -> dict:
        size = self.length(8192)
        data = self.read_body(size)
        if len(data) != size:
            raise ApiError(400, "Неполные данные.")
        try:
            value = json.loads(data)
        except (ValueError, UnicodeError):
            raise ApiError(400, "Некорректный JSON.")
        if not isinstance(value, dict):
            raise ApiError(400, "Ожидался JSON-объект.")
        return value

    def dispatch(self):
        try:
            raw_length = self.headers.get("Content-Length", "")
            if (self.command in ("PUT", "POST") and len(raw_length) <= 16
                    and raw_length.isascii() and raw_length.isdigit()):
                self.body_remaining = int(raw_length)
            self.server.share.authenticate(
                self.client_address[0], self.headers.get("Authorization", ""))
            url = urlsplit(self.path)
            params = parse_qs(url.query, keep_blank_values=True)
            path = params.get("path", [""])[0]
            share = self.server.share
            if self.command == "GET" and url.path == "/api/status":
                self.reply(200, {"version": API_VERSION, "computer": socket.gethostname(),
                                 "folder": share.root.name, "readOnly": share.read_only,
                                 "maxUpload": share.max_upload})
            elif self.command == "GET" and url.path == "/api/files":
                directory = share.path(path)
                if not directory.is_dir():
                    raise ApiError(404, "Папка не найдена.")
                entries = []
                for child in directory.iterdir():
                    try:
                        relative = child.relative_to(share.root).as_posix()
                        child = share.path(relative)
                        info = child.stat()
                        if not stat.S_ISDIR(info.st_mode) and (
                                not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
                            continue
                        entries.append({"name": child.name, "path": relative,
                                        "directory": child.is_dir(), "size": info.st_size,
                                        "modified": int(info.st_mtime * 1000)})
                    except (OSError, ApiError):
                        continue
                    if len(entries) > 10000:
                        raise ApiError(413, "В папке больше 10000 элементов.")
                entries.sort(key=lambda entry: (not entry["directory"], entry["name"].casefold()))
                self.reply(200, {"path": path, "entries": entries})
            elif self.command == "GET" and url.path == "/api/download":
                file = share.path(path)
                if not file.is_file():
                    raise ApiError(404, "Файл не найден.")
                with file.open("rb") as source:
                    info = os.fstat(source.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise ApiError(403, "Этот тип файла недоступен.")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(info.st_size))
                    self.send_header("Content-Disposition",
                                     "attachment; filename*=UTF-8''" + quote(file.name))
                    self.end_headers()
                    remaining = info.st_size
                    while remaining and (data := source.read(min(CHUNK, remaining))):
                        self.wfile.write(data)
                        remaining -= len(data)
            elif self.command == "PUT" and url.path == "/api/upload":
                self.upload(path, params.get("name", [""])[0])
            elif self.command == "POST" and url.path == "/api/folders":
                share.writable()
                body = self.json_body()
                parent = body.get("path", "")
                name = body.get("name", "")
                if not isinstance(parent, str) or not isinstance(name, str):
                    raise ApiError(400, "Имя и путь должны быть строками.")
                folder = share.path(parent) / valid_name(name)
                with share.mutation_lock:
                    folder.mkdir()
                self.reply(201, {"ok": True})
            else:
                raise ApiError(404, "Метод API не найден.")
        except ApiError as error:
            self.reply(error.status, {"error": str(error)})
        except FileExistsError:
            self.reply(409, {"error": "Элемент с таким именем уже существует."})
        except FileNotFoundError:
            self.reply(404, {"error": "Файл или папка не найдены."})
        except PermissionError:
            self.reply(403, {"error": "Операционная система запретила доступ."})
        except (BrokenPipeError, ConnectionResetError, TimeoutError, ssl.SSLError):
            pass
        except OSError:
            self.reply(500, {"error": "Ошибка ввода-вывода на ПК."})

    def upload(self, relative: str, name: str):
        share = self.server.share
        share.writable()
        length = self.length(share.max_upload)
        folder = share.path(relative)
        if not folder.is_dir():
            raise ApiError(404, "Папка не найдена.")
        target = folder / valid_name(name)
        if target.exists():
            raise ApiError(409, "Файл уже существует. Выберите другое имя.")
        fd, temp = tempfile.mkstemp(prefix=".pcremote-", dir=folder)
        try:
            with os.fdopen(fd, "wb") as output:
                remaining = length
                while remaining:
                    data = self.read_body(min(CHUNK, remaining))
                    if not data:
                        raise ApiError(400, "Загрузка прервана.")
                    output.write(data)
                    remaining -= len(data)
                output.flush()
                os.fsync(output.fileno())
            with share.mutation_lock:
                if os.name == "nt":
                    # Unlike POSIX rename, Windows rename fails if the destination exists.
                    os.rename(temp, target)
                else:
                    # POSIX hard-link publication is atomic and never overwrites.
                    os.link(temp, target)
                    Path(temp).unlink()
            self.reply(201, {"ok": True, "name": name, "size": length})
        finally:
            Path(temp).unlink(missing_ok=True)

    do_GET = dispatch
    do_PUT = dispatch
    do_POST = dispatch
    do_DELETE = dispatch


def identity(state: Path, rotate: bool = False) -> tuple[str, str, Path, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    token_path = state / "token.txt"
    cert_path, key_path = state / "certificate.pem", state / "private-key.pem"
    if rotate or not token_path.exists():
        token_path.write_text(secrets.token_urlsafe(32), encoding="ascii")
        token_path.chmod(0o600)
    if not cert_path.exists() or not key_path.exists():
        key = ec.generate_private_key(ec.SECP256R1())
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PC Remote")])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=5))
                .not_valid_after(now + timedelta(days=3650))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .sign(key, hashes.SHA256()))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                               serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
        key_path.chmod(0o600)
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    fingerprint = cert.fingerprint(hashes.SHA256()).hex().upper()
    return token_path.read_text(encoding="ascii").strip(), fingerprint, cert_path, key_path


def local_addresses() -> list[str]:
    addresses = {"127.0.0.1"}
    try:
        addresses.update(socket.gethostbyname_ex(socket.gethostname())[2])
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 1))  # route discovery, no packets sent
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass
    return sorted(addresses)


def main():
    parser = argparse.ArgumentParser(description="Защищённая общая папка PC Remote")
    parser.add_argument("--root", type=Path, required=True, help="Только эта папка будет доступна")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--rotate-token", action="store_true")
    parser.add_argument("--state", type=Path,
                        default=Path(os.getenv("LOCALAPPDATA", Path.home() / ".local/share"))
                        / "PCRemote")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if args.state.resolve().is_relative_to(root):
        parser.error("Секреты --state должны находиться ВНЕ общей папки --root.")
    token, fingerprint, cert, key = identity(args.state, args.rotate_token)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(cert, key)
    server = FileServer((args.host, args.port), Share(root, token, args.read_only), tls)
    print("\n  PC REMOTE — доступ к выбранной папке\n", flush=True)
    print(f"  Папка: {root}\n  Только чтение: {args.read_only}")
    for address in local_addresses() if args.host == "0.0.0.0" else [args.host]:
        print(f"  Адрес: https://{address}:{server.server_port}")
    print(f"\n  Ключ доступа: {token}\n\n  SHA-256 сертификата:\n  {fingerprint}")
    print("\n  Введите эти данные на телефоне. Не передавайте их посторонним.")
    print("  Для интернета используйте личный VPN. Не пробрасывайте порт на роутере.")
    print("  Остановка: Ctrl+C. Сервер не устанавливается в автозагрузку.\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
