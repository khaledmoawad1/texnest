#!/usr/bin/env python3
"""
Compile self-test for the local Overleaf: proves the image can build the kinds of
documents used on overleaf.com. Run after every upgrade / image rebuild:

    ./overleaf selftest            (or: python3 scripts/selftest_compile.py)

For each folder in scripts/selftest/ it zips the sources, uploads them as a
project (same endpoint as the dashboard's "Upload Project"), sets the compiler,
compiles, checks that a PDF was produced with no LaTeX errors, and deletes the
project again. Exit code 0 = everything passed.

Credentials: env LOCAL_OVERLEAF_URL / LOCAL_OVERLEAF_EMAIL / LOCAL_OVERLEAF_PASSWORD,
or migration/.local-credentials (written at setup time).
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = [("pdflatex", "pdflatex"), ("xelatex", "xelatex"), ("beamer", "pdflatex")]  # (folder, compiler)


def creds():
    env = {k: os.environ.get(k) for k in ("LOCAL_OVERLEAF_URL", "LOCAL_OVERLEAF_EMAIL", "LOCAL_OVERLEAF_PASSWORD")}
    f = ROOT / "migration" / ".local-credentials"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k, None)
                env[k] = env[k] or v.strip()
    if not env.get("LOCAL_OVERLEAF_EMAIL") or not env.get("LOCAL_OVERLEAF_PASSWORD"):
        sys.exit("no credentials: set LOCAL_OVERLEAF_EMAIL/PASSWORD or create migration/.local-credentials")
    return env.get("LOCAL_OVERLEAF_URL") or "http://localhost", env["LOCAL_OVERLEAF_EMAIL"], env["LOCAL_OVERLEAF_PASSWORD"]


class Client:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.csrf = None

    def page(self, path):
        html = self.op.open(self.base + path, timeout=60).read().decode()
        m = re.search(r'<meta\s+name="ol-csrfToken"\s+content="([^"]+)"', html)
        if m:
            self.csrf = m.group(1)
        return html

    def post(self, path, payload, timeout=400):
        req = urllib.request.Request(self.base + path, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "x-csrf-token": self.csrf,
                                              "Accept": "application/json"})
        body = self.op.open(req, timeout=timeout).read().decode()
        try:
            return json.loads(body) if body.strip() else None
        except json.JSONDecodeError:
            return {"raw": body}

    def delete(self, path):
        self.op.open(urllib.request.Request(self.base + path, method="DELETE", headers={"x-csrf-token": self.csrf}))

    def upload(self, name, zip_bytes):
        bnd = "----selftest" + uuid.uuid4().hex
        body = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\n{name}\r\n"
                f"--{bnd}\r\nContent-Disposition: form-data; name=\"qqfile\"; filename=\"{name}.zip\"\r\n"
                f"Content-Type: application/zip\r\n\r\n").encode() + zip_bytes + f"\r\n--{bnd}--\r\n".encode()
        req = urllib.request.Request(self.base + "/project/new/upload", data=body, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={bnd}",
                                              "x-csrf-token": self.csrf, "Accept": "application/json"})
        res = json.loads(self.op.open(req, timeout=300).read().decode())
        if not res.get("success"):
            raise RuntimeError(f"upload failed: {res}")
        return res["project_id"]


def zip_dir(d):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(Path(d).rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(d))
    return buf.getvalue()


def main():
    base, email, password = creds()
    c = Client(base)
    c.page("/login")
    c.post("/login", {"email": email, "password": password})
    c.page("/project")
    all_ok = True
    for folder, compiler in CASES:
        src = ROOT / "scripts" / "selftest" / folder
        pid = c.upload(f"selftest-{folder}", zip_dir(src))
        try:
            c.post(f"/project/{pid}/settings", {"compiler": compiler})
            t = time.time()
            out = c.post(f"/project/{pid}/compile", {"rootDoc_id": None, "draft": False, "check": "silent",
                                                     "incrementalCompilesEnabled": False})
            dt = time.time() - t
            files = {o["path"]: o["url"] for o in out.get("outputFiles", [])}
            log = c.op.open(base + files["output.log"]).read().decode("utf-8", "replace") if "output.log" in files else ""
            errors = [l for l in log.splitlines() if l.startswith("!")][:5]
            ok = out.get("status") == "success" and "output.pdf" in files and not errors
            all_ok &= ok
            engine = log.splitlines()[0][:60] if log else "?"
            print(f"[{'PASS' if ok else 'FAIL'}] {folder:9s} {compiler:8s} {dt:5.1f}s  {engine}")
            for e in errors:
                print("        ", e)
        finally:
            c.post(f"/project/{pid}/trash", {})
            c.delete(f"/project/{pid}")
    print("ALL PASSED" if all_ok else "SOME FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
