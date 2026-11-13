"""Integration tests use a real TLS listener, temporary files and fresh identities."""
import concurrent.futures
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))
from server import FileServer, Share, identity


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "shared"
        self.root.mkdir()
        (self.root / "папка").mkdir()
        (self.root / "hello.txt").write_text("Привет!\n", encoding="utf-8")
        (self.base / "secret.txt").write_text("private", encoding="utf-8")
        self.token, self.pin, cert, key = identity(self.base / "state")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert, key)
        self.share = Share(self.root, self.token)
        self.server = FileServer(("127.0.0.1", 0), self.share, context)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client_context = ssl.create_default_context(cafile=str(cert))
        # Certificate identity is validated separately by the exact SHA-256 pin.
        self.client_context.check_hostname = False

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, method="GET", path="/api/status", body=None, auth=True, headers=None):
        conn = http.client.HTTPSConnection("127.0.0.1", self.port,
                                          context=self.client_context, timeout=5)
        head = {"Authorization": "Bearer " + self.token} if auth else {}
        head.update(headers or {})
        conn.request(method, path, body, head)
        response = conn.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        conn.close()
        return result

    def test_status_and_tls_fingerprint(self):
        status, data, headers = self.request()
        self.assertEqual(200, status)
        self.assertEqual(1, json.loads(data)["version"])
        self.assertEqual("no-store", headers["Cache-Control"])
        with socket.create_connection(("127.0.0.1", self.port)) as sock:
            with self.client_context.wrap_socket(sock, server_hostname="PC Remote") as tls:
                self.assertEqual(self.pin, hashlib.sha256(
                    tls.getpeercert(binary_form=True)).hexdigest().upper())

    def test_missing_token(self):
        for route in ("/api/status", "/api/files", "/api/download?path=hello.txt"):
            self.assertEqual(401, self.request(path=route, auth=False)[0])

    def test_wrong_token_and_scheme(self):
        self.assertEqual(401, self.request(headers={"Authorization": "Bearer wrong"})[0])
        self.assertEqual(401, self.request(headers={"Authorization": self.token})[0])

    def test_rate_limit(self):
        for _ in range(12):
            self.assertEqual(401, self.request(auth=False)[0])
        self.assertEqual(429, self.request(auth=False)[0])

    def test_list_directory_first(self):
        code, body, _ = self.request(path="/api/files")
        self.assertEqual(200, code)
        listing = json.loads(body)["entries"]
        self.assertEqual("папка", listing[0]["name"])
        self.assertTrue(listing[0]["directory"])
        self.assertEqual("hello.txt", listing[1]["path"])

    def test_download(self):
        code, data, headers = self.request(path="/api/download?path=hello.txt")
        self.assertEqual(200, code)
        self.assertEqual((self.root / "hello.txt").read_bytes(), data)
        self.assertIn("attachment", headers["Content-Disposition"])

    def test_traversal_blocked(self):
        for path in ("../secret.txt", "/etc/passwd", r"..\secret.txt",
                     "C:/Windows/win.ini", "hello.txt:secret", "папка/../../secret.txt"):
            with self.subTest(path=path):
                self.assertEqual(403, self.request(path="/api/download?path=" + quote(path))[0])

    def test_encoded_traversal(self):
        self.assertEqual(403, self.request(path="/api/download?path=%2e%2e%2fsecret.txt")[0])
        self.assertNotEqual(200, self.request(path="/api/download?path=%252e%252e%252fsecret.txt")[0])

    def test_symbolic_link(self):
        link = self.root / "external"
        try:
            link.symlink_to(self.base / "secret.txt")
        except OSError:
            self.skipTest("Windows requires developer mode or privilege for symlinks")
        self.assertEqual(403, self.request(path="/api/download?path=external")[0])
        body = self.request(path="/api/files")[1]
        self.assertNotIn("external", body.decode())

    def test_hardlink_cannot_alias_private_file(self):
        link = self.root / "linked.txt"
        try:
            os.link(self.base / "secret.txt", link)
        except OSError:
            self.skipTest("Temporary filesystem does not support hard links")
        self.assertEqual(403, self.request(path="/api/download?path=linked.txt")[0])
        self.assertNotIn("linked.txt", self.request(path="/api/files")[1].decode())

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_junction(self):
        private = self.base / "private"
        private.mkdir()
        (private / "secret.txt").write_text("secret")
        link = self.root / "junction"
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(private)],
                       check=True, capture_output=True)
        try:
            self.assertEqual(403, self.request(path="/api/download?path=junction/secret.txt")[0])
            self.assertNotIn("junction", self.request(path="/api/files")[1].decode())
        finally:
            link.rmdir()

    def test_upload_and_unicode_filename(self):
        name = "Отчёт за ноябрь.txt"
        payload = "Данные с телефона".encode()
        code = self.request("PUT", "/api/upload?name=" + quote(name), payload)[0]
        self.assertEqual(201, code)
        self.assertEqual(payload, (self.root / name).read_bytes())
        self.assertFalse(list(self.root.glob(".pcremote-*")))

    def test_upload_into_subfolder(self):
        self.assertEqual(201, self.request(
            "PUT", "/api/upload?path=" + quote("папка") + "&name=a.bin", b"abc")[0])
        self.assertEqual(b"abc", (self.root / "папка/a.bin").read_bytes())

    def test_overwrite_forbidden(self):
        before = (self.root / "hello.txt").read_bytes()
        self.assertEqual(409, self.request("PUT", "/api/upload?name=hello.txt", b"replacement")[0])
        self.assertEqual(before, (self.root / "hello.txt").read_bytes())

    def test_concurrent_upload_never_overwrites(self):
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            jobs = [pool.submit(self.request, "PUT", "/api/upload?name=race.bin", bytes([i]) * 65536)
                    for i in (1, 2)]
            self.assertEqual([201, 409], sorted(job.result()[0] for job in jobs))
        self.assertIn((self.root / "race.bin").read_bytes(), (b"\1" * 65536, b"\2" * 65536))
        self.assertFalse(list(self.root.glob(".pcremote-*")))

    def test_empty_file(self):
        self.assertEqual(201, self.request("PUT", "/api/upload?name=empty.txt", b"")[0])
        self.assertEqual(0, (self.root / "empty.txt").stat().st_size)

    def test_size_limit(self):
        self.share.max_upload = 2
        self.assertEqual(413, self.request("PUT", "/api/upload?name=big.txt", b"too big")[0])
        self.assertFalse((self.root / "big.txt").exists())

    def test_dangerous_upload_names(self):
        for name in ("../escape", "x:y", "NUL", "CON.txt", "com1", "COM¹.txt",
                     "NUL .txt", "end.", ".pcremote-temp"):
            with self.subTest(name=name):
                code = self.request("PUT", "/api/upload?name=" + quote(name), b"x")[0]
                self.assertEqual(400, code)

    def test_read_only(self):
        self.share.read_only = True
        self.assertEqual(200, self.request(path="/api/files")[0])
        self.assertEqual(403, self.request("PUT", "/api/upload?name=no.txt", b"x")[0])
        self.assertEqual(403, self.request("POST", "/api/folders", b'{"name":"no"}')[0])

    def test_mkdir(self):
        self.assertEqual(201, self.request("POST", "/api/folders", b'{"name":"new"}')[0])
        self.assertTrue((self.root / "new").is_dir())
        self.assertEqual(409, self.request("POST", "/api/folders", b'{"name":"new"}')[0])

    def test_invalid_json(self):
        for body in (b"[]", b"{", b'{"name":123}', b'{"path":[],"name":"a"}'):
            self.assertEqual(400, self.request("POST", "/api/folders", body)[0])

    def test_delete_not_supported(self):
        self.assertEqual(404, self.request("DELETE", "/api/download?path=hello.txt")[0])
        self.assertTrue((self.root / "hello.txt").exists())

    def test_identity_persistence_and_token_rotation(self):
        token, pin, _, _ = identity(self.base / "state")
        self.assertEqual((self.token, self.pin), (token, pin))
        token, pin, _, _ = identity(self.base / "state", rotate=True)
        self.assertNotEqual(self.token, token)
        self.assertEqual(self.pin, pin)

    def test_private_temp_files_are_not_listed(self):
        (self.root / ".pcremote-incomplete").write_text("partial")
        listing = json.loads(self.request(path="/api/files")[1])["entries"]
        self.assertNotIn(".pcremote-incomplete", [e["name"] for e in listing])

    def test_wrong_certificate_is_rejected(self):
        _, _, other_cert, _ = identity(self.base / "other-state")
        context = ssl.create_default_context(cafile=str(other_cert))
        context.check_hostname = False
        conn = http.client.HTTPSConnection("127.0.0.1", self.port, context=context, timeout=3)
        try:
            with self.assertRaises(ssl.SSLCertVerificationError):
                conn.request("GET", "/api/status")
        finally:
            conn.close()

    @unittest.skipUnless(os.name == "nt", "Windows launcher test")
    def test_powershell_launcher(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        environment = os.environ.copy()
        environment["LOCALAPPDATA"] = str(self.base / "launcher-state")
        process = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(Path(__file__).resolve().parents[1] / "start-server.ps1"),
             "-Root", str(self.root), "-BindAddress", "127.0.0.1", "-Port", str(port), "-ReadOnly"],
            env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            state = Path(environment["LOCALAPPDATA"]) / "PCRemote"
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    self.fail(process.stderr.read().decode("utf-8", "replace"))
                if (state / "certificate.pem").exists():
                    try:
                        context = ssl.create_default_context(cafile=str(state / "certificate.pem"))
                        context.check_hostname = False
                        connection = http.client.HTTPSConnection("127.0.0.1", port,
                                                                 context=context, timeout=1)
                        connection.request("GET", "/api/status", headers={
                            "Authorization": "Bearer " + (state / "token.txt").read_text("ascii")})
                        response = connection.getresponse()
                        self.assertEqual(200, response.status)
                        self.assertTrue(json.loads(response.read())["readOnly"])
                        connection.close()
                        break
                    except (ConnectionError, OSError):
                        pass
                time.sleep(.1)
            else:
                self.fail("PowerShell launcher did not start in 15 seconds.")
        finally:
            subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True)
            process.wait(timeout=10)
            process.stderr.close()


if __name__ == "__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
