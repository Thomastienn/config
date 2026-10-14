#!/usr/bin/env python3
"""Run with xvfb-run -a /usr/bin/python3 scripts/test-quick-tools.py."""

from contextlib import ExitStack
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import zipfile

spec = importlib.util.spec_from_file_location("quick_tools", Path(__file__).with_name("quick-tools.py"))
toolbox = importlib.util.module_from_spec(spec)
spec.loader.exec_module(toolbox)


def archive(files):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as output:
        for path, content in files.items():
            output.writestr(path, content)
    return data.getvalue()


class QuickToolsTests(unittest.TestCase):
    def setUp(self):
        self.context = ExitStack()
        self.addCleanup(self.context.close)
        directory = self.context.enter_context(tempfile.TemporaryDirectory())
        self.data = Path(directory)
        self.app = self.data / "dist"
        self.app.mkdir()
        (self.app / "index.html").write_text("toolbox fixture")
        (self.app / "asset.js").write_text("fixture script")
        self.context.enter_context(patch.object(toolbox, "DATA", self.data))
        self.context.enter_context(patch.object(toolbox, "APP", self.app))

    def start_server(self, server):
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.context.callback(server.server_close)
        self.context.callback(thread.join, 2)
        self.context.callback(server.shutdown)
        self.context.enter_context(patch.object(toolbox, "ORIGIN", f"http://127.0.0.1:{server.server_port}"))
        return server

    def test_catalogue(self):
        tools = toolbox.tools()
        self.assertEqual(len(tools), 86)
        self.assertEqual(len({tool["path"] for tool in tools}), 86)
        for tool in tools:
            self.assertRegex(tool["path"], r"^/[a-z0-9-]+$")
            self.assertTrue(tool["title"] and tool["description"] and tool["aliases"])
            for term in [tool["title"], tool["description"], *tool["keywords"], *tool["aliases"]]:
                self.assertFalse(any(character in term for character in "\r\n\t\0"))

    def test_install_preserves_profile_and_repairs_assets(self):
        (self.data / "browser").mkdir()
        profile = self.data / "browser" / "keep"
        profile.write_text("profile data")
        data = archive({"dist/index.html": "new app", "dist/assets/tool.js": "new script"})
        with patch.object(toolbox, "SHA256", hashlib.sha256(data).hexdigest()):
            toolbox.install_archive(data)
            (self.app / "assets/tool.js").unlink()
            toolbox.install_archive(data)
        self.assertEqual((self.app / "index.html").read_text(), "new app")
        self.assertEqual((self.app / "assets/tool.js").read_text(), "new script")
        self.assertEqual(profile.read_text(), "profile data")

    def test_bad_checksum_keeps_existing_app(self):
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            toolbox.install_archive(b"bad release")
        self.assertEqual((self.app / "index.html").read_text(), "toolbox fixture")

    def test_unsafe_zip_and_missing_app_are_rejected(self):
        for path in ["dist/../../escape", "/dist/escape", "outside/file", "dist\\escape", "dist/asset.js"]:
            with self.subTest(path=path):
                data = archive({path: "untrusted"})
                with patch.object(toolbox, "SHA256", hashlib.sha256(data).hexdigest()):
                    with self.assertRaises(RuntimeError):
                        toolbox.install_archive(data)
                self.assertEqual((self.app / "index.html").read_text(), "toolbox fixture")
        self.assertFalse((self.data.parent / "escape").exists())

    def test_local_server_routes_assets_and_reuse(self):
        with patch.object(toolbox, "ADDRESS", ("127.0.0.1", 0)):
            server = self.start_server(toolbox.make_server())
        self.assertEqual(server.server_address[0], "127.0.0.1")
        self.assertTrue(toolbox.server_ready())
        for path, expected in [("/", b"toolbox fixture"), ("/base64-string-converter", b"toolbox fixture"),
                               ("/asset.js", b"fixture script")]:
            with toolbox.LOCAL_HTTP.open(toolbox.ORIGIN + path) as response:
                self.assertEqual(response.read(), expected)
        for path in ["/assets/missing.js", "/not-a-tool", "/../server.lock"]:
            with self.assertRaises(urllib.error.HTTPError) as error:
                toolbox.LOCAL_HTTP.open(toolbox.ORIGIN + path)
            self.assertEqual(error.exception.code, 404)
        with patch.object(toolbox.subprocess, "Popen") as spawn:
            toolbox.ensure_server()
            toolbox.ensure_server()
            spawn.assert_not_called()

    def test_occupied_port_is_not_treated_as_toolbox(self):
        class OtherApp(SimpleHTTPRequestHandler):
            def log_message(self, *_args):
                pass
        self.start_server(ThreadingHTTPServer(("127.0.0.1", 0), OtherApp))
        with self.assertRaisesRegex(RuntimeError, "occupied"):
            toolbox.server_ready()

    def test_cancel_has_no_side_effects(self):
        for code in [0, 1]:
            with patch.object(toolbox.subprocess, "run", return_value=subprocess.CompletedProcess([], code, "", "")), \
                 patch.object(toolbox, "ensure_server") as start, \
                 patch.object(toolbox.subprocess, "Popen") as spawn:
                toolbox.launch()
                start.assert_not_called()
                spawn.assert_not_called()

    def test_selection_opens_only_tool_route(self):
        catalogue = toolbox.tools()
        index = next(i for i, tool in enumerate(catalogue, 1) if tool["path"] == "/json-prettify")
        with patch.object(toolbox.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, str(index), "")), \
             patch.object(toolbox, "ensure_server") as start, \
             patch.object(toolbox.shutil, "which", return_value="/usr/bin/brave-browser"), \
             patch.object(toolbox.subprocess, "Popen") as spawn:
            toolbox.launch()
            start.assert_called_once()
            arguments = spawn.call_args.args[0]
            self.assertIn("--app=" + toolbox.ORIGIN + "/json-prettify", arguments)
            self.assertIn("--class=quick-tools", arguments)
            self.assertNotIn("shell", spawn.call_args.kwargs)
        for value in ["-1", "9999", "not an index"]:
            with patch.object(toolbox.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, value, "")), \
                 patch.object(toolbox, "ensure_server") as start:
                with self.assertRaises((ValueError, RuntimeError)):
                    toolbox.launch()
                start.assert_not_called()

    @unittest.skipUnless(shutil.which("rofi") and shutil.which("xdotool") and os.environ.get("DISPLAY"),
                         "Rofi search check needs X11/Xvfb and xdotool")
    def test_real_rofi_phrase_search(self):
        with patch.object(toolbox.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "")) as menu:
            toolbox.launch()
        arguments = menu.call_args.args[0] + ["-config", str(toolbox.ROOT.parent / "rofi/config.rasi")]
        rows = menu.call_args.kwargs["input"]
        catalogue = [{"path": "/", "title": "Browse all tools"}, *toolbox.tools()]
        queries = {"decode base64": "/base64-string-converter", "make json readable": "/json-prettify",
                   "remove url escapes": "/url-encoder", "count words": "/text-statistics",
                   "unix timestamp": "/date-converter", "generate uuid": "/uuid-generator",
                   "random password": "/token-generator", "b64": "/base64-string-converter"}
        for query, expected in queries.items():
            with self.subTest(query=query):
                result = subprocess.run(arguments + ["-filter", query, "-dump"], input=rows,
                                        capture_output=True, text=True, check=True)
                matches = [catalogue[int(index)]["path"] for index in result.stdout.splitlines()]
                self.assertLessEqual(len(matches), 3, (query, matches))
                self.assertIn(expected, matches, query)
                # -dump preserves input order; accept the actual UI's first result too.
                with subprocess.Popen(arguments + ["-filter", query],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True) as process:
                    process.stdin.write(rows)
                    process.stdin.close()
                    process.stdin = None
                    subprocess.run(["xdotool", "search", "--sync", "--class", "rofi"],
                                   capture_output=True, timeout=5, check=True)
                    subprocess.run(["xdotool", "key", "Return"], check=True)
                    selected, errors = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 0, errors)
                actual = catalogue[int(selected)]["path"]
                allowed = {expected, "/base64-file-converter"} if "64" in query else {expected}
                self.assertIn(actual, allowed, query)


if __name__ == "__main__":
    unittest.main()
