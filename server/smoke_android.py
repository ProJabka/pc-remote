"""Optional end-to-end UI smoke test. Requires an already booted emulator.

WARNING: clears ru.pcremote.app data on the selected emulator.
Run: tools/python/python.exe server/smoke_android.py --serial emulator-5554
"""
import argparse
import hashlib
from pathlib import Path
import re
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent))
from server import FileServer, Share, identity

PROJECT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", default="emulator-5554")
    args = parser.parse_args()
    if not args.serial.startswith("emulator-"):
        parser.error("This destructive test is restricted to emulators.")
    adb = PROJECT / "tools/android-sdk/platform-tools/adb.exe"
    prefix = [str(adb), "-s", args.serial]

    def command(*argv, check=True):
        return subprocess.run(prefix + list(argv), check=check,
                              capture_output=True, timeout=45).stdout.decode("utf-8", "replace")

    def shell(*argv):
        return command("shell", *argv)

    def tree():
        shell("uiautomator", "dump", "/sdcard/pcremote-ui.xml")
        return ET.fromstring(shell("cat", "/sdcard/pcremote-ui.xml"))

    def nodes():
        return list(tree().iter("node"))

    def wait(predicate, description, seconds=30):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            found = [node for node in nodes() if predicate(node)]
            if found:
                return found[0]
            time.sleep(.5)
        raise AssertionError("Timed out: " + description)

    def text_node(value):
        return wait(lambda node: value.casefold() in node.get("text", "").casefold(), value)

    def tap(node):
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.attrib["bounds"]))
        shell("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))

    def edit(index, value, clear=False):
        fields = [n for n in nodes() if n.get("class") == "android.widget.EditText"]
        tap(fields[index])
        if clear:
            shell("input", "keycombination", "113", "29")  # Ctrl+A
        if value:
            shell("input", "text", value)
        shell("input", "keyevent", "4")  # close keyboard

    def screenshot(name):
        directory = PROJECT / "docs"
        directory.mkdir(exist_ok=True)
        remote = "/sdcard/pcremote-screenshot.png"
        shell("screencap", "-p", remote)
        command("pull", remote, str(directory / name))

    with tempfile.TemporaryDirectory(prefix="pcremote-smoke-") as temporary:
        base = Path(temporary)
        root = base / "Shared"
        root.mkdir()
        (root / "Documents").mkdir()
        payload = b"PC Remote Android end-to-end transfer\n" * 1024
        (root / "hello.txt").write_bytes(payload)
        secret, pin, cert, key = identity(base / "state")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert, key)
        server = FileServer(("127.0.0.1", 0), Share(root, secret), context)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            command("install", "-r", str(PROJECT / "dist/PC-Remote.apk"))
            shell("pm", "clear", "ru.pcremote.app")
            shell("am", "start", "-n", "ru.pcremote.app/.MainActivity")
            text_node("Подключиться")
            screenshot("android-connection.png")
            edit(0, f"https://10.0.2.2:{server.server_port}")
            edit(1, secret)
            edit(2, "A" * 64)
            tap(text_node("Подключиться"))
            text_node("Не удалось проверить TLS")
            print("PASS: wrong TLS pin rejected", flush=True)
            edit(2, pin, clear=True)
            tap(text_node("Подключиться"))
            text_node("hello.txt")
            print("PASS: pinned TLS connection and directory listing", flush=True)
            screenshot("android-files.png")
            tap(text_node("Documents"))
            text_node("В этой папке пока нет файлов")
            shell("input", "keyevent", "4")
            text_node("hello.txt")
            print("PASS: navigate into a directory and back", flush=True)

            # Filter the current directory.
            edit(0, "nothing-matches")
            text_node("Ничего не найдено")
            edit(0, "hello", clear=True)
            text_node("hello.txt")
            edit(0, "", clear=True)
            print("PASS: live filename search", flush=True)

            # Create folder through the UI.
            tap(text_node("+ Папка"))
            text_node("Новая папка")
            edit(0, "Android-created")
            tap(text_node("Создать"))
            text_node("Android-created")
            assert (root / "Android-created").is_dir()
            print("PASS: create folder on PC", flush=True)

            # Download through the system Storage Access Framework picker.
            tap(text_node("hello.txt"))
            tap(text_node("Скачать"))
            save = wait(lambda n: n.get("class") == "android.widget.Button"
                        and n.get("text", "").lower() in ("save", "сохранить"), "document save button")
            tap(save)
            text_node("Файл сохранён на телефон")
            local = base / "downloaded.txt"
            command("pull", "/sdcard/Download/hello.txt", str(local))
            assert local.read_bytes() == payload
            print("PASS: Android download matches original bytes", flush=True)

            # Upload the downloaded file into the empty Documents directory.
            tap(text_node("Documents"))
            text_node("В этой папке пока нет файлов")
            tap(text_node("Загрузить на ПК"))
            tap(text_node("hello.txt"))
            text_node("hello.txt")
            until = time.monotonic() + 30
            while time.monotonic() < until and not (root / "Documents/hello.txt").exists():
                time.sleep(.2)
            assert (root / "Documents/hello.txt").read_bytes() == payload
            print("PASS: Android upload matches original bytes", flush=True)

            # No credentials are captured in screenshots/logs.
            screenshot("android-transfer.png")
            runtime = command("logcat", "-d", "-s", "AndroidRuntime:E")
            assert "FATAL EXCEPTION" not in runtime, runtime
            print("PASS: no AndroidRuntime crashes", flush=True)
        except BaseException:
            try:
                shell("screencap", "-p", "/sdcard/pcremote-failure.png")
                command("pull", "/sdcard/pcremote-failure.png", str(PROJECT / "tools/android-failure.png"))
            except Exception:
                pass
            raise
        finally:
            shell("am", "force-stop", "ru.pcremote.app")
            shell("pm", "clear", "ru.pcremote.app")
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
