#!/usr/bin/env python3
"""
Import projects (zips) into the LOCAL Overleaf instance and rebuild the dashboard layout.

Reads migration/manifest.json (written by export_overleaf_projects.py) and, for
each project that has a zip:
  * uploads the zip through the same endpoint the "Upload Project" button uses
    (POST /project/new/upload), giving it the original project name,
  * re-creates every tag (the dashboard folders) and puts the projects in them,
  * re-applies the archived / trashed flags,
  * copies your name and editor preferences (theme, font, keybindings, PDF viewer,
    spell-check language, ...) so the editor looks the same as on overleaf.com,
  * records old-id -> new-id in migration/import-state.json so re-running the
    script never creates duplicates (already-imported projects are skipped).

Usage:
  python3 scripts/import_projects.py --email you@example.com --password '...'
  (defaults: --url http://localhost, manifest + zips under ./migration)

Only the Python standard library is used.
"""
import argparse
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookiejar import CookieJar
from pathlib import Path


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


class Local:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = None

    def _req(self, path, data=None, method=None, headers=None, timeout=300):
        h = {"Accept": "application/json, text/html;q=0.9", "User-Agent": "overleaf-local-migration/1.0"}
        if self.csrf:
            h["x-csrf-token"] = self.csrf
        if headers:
            h.update(headers)
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        return self.opener.open(req, timeout=timeout)

    def get_text(self, path):
        with self._req(path) as r:
            return r.geturl(), r.read().decode("utf-8", "replace")

    def refresh_csrf(self, path="/project"):
        """CSRF token is sent in the x-csrf-token header (never in bodies: several
        endpoints use strict schemas that reject unknown body keys)."""
        _, page = self.get_text(path)
        m = re.search(r'<meta\s+name="ol-csrfToken"\s+content="([^"]+)"', page)
        if not m:
            m = re.search(r'name="_csrf"\s+value="([^"]+)"', page)
        if not m:
            raise RuntimeError(f"could not find a CSRF token on {path}")
        self.csrf = m.group(1)
        return page

    def post_json(self, path, payload, timeout=300):
        data = json.dumps(payload).encode()
        with self._req(path, data=data, method="POST",
                       headers={"Content-Type": "application/json"}, timeout=timeout) as r:
            body = r.read().decode()
            try:
                return json.loads(body) if body.strip() else None
            except json.JSONDecodeError:
                # some endpoints (archive/trash/tag) answer with plain text or HTML
                return {"raw": body[:200], "status": r.status}

    def delete(self, path):
        with self._req(path, method="DELETE") as r:
            return r.status

    def post_multipart(self, path, fields, file_field, filename, filepath, timeout=900):
        boundary = "----overleafmigration" + uuid.uuid4().hex
        body = bytearray()
        for k, v in fields.items():
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        ctype = mimetypes.guess_type(filename)[0] or "application/zip"
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
                 f"filename=\"{filename}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
        body += Path(filepath).read_bytes()
        body += f"\r\n--{boundary}--\r\n".encode()
        with self._req(path, data=bytes(body), method="POST",
                       headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                       timeout=timeout) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt.strip() else None

    # ---- high level ----
    def login(self, email, password):
        self.refresh_csrf("/login")
        try:
            res = self.post_json("/login", {"email": email, "password": password})
        except urllib.error.HTTPError as e:
            sys.exit(f"ERROR: login failed (HTTP {e.code}): {e.read().decode()[:300]}")
        if isinstance(res, dict) and res.get("message") and res["message"].get("type") == "error":
            sys.exit(f"ERROR: login rejected: {res['message'].get('text')}")
        # a fresh CSRF token is issued after login
        self.refresh_csrf("/project")
        log(f"logged in to {self.base} as {email}")

    def list_projects(self):
        page = self.refresh_csrf("/project")
        m = re.search(r'<meta\s+name="ol-prefetchedProjectsBlob"\s+(?:data-type="json"\s+)?content="([^"]*)"', page)
        if m:
            import html
            return json.loads(html.unescape(m.group(1))).get("projects", [])
        try:
            res = self.post_json("/api/project", {"filters": {}, "page": {"size": 500},
                                                  "sort": {"by": "lastUpdated", "order": "desc"}})
            return res.get("projects", []) if isinstance(res, dict) else []
        except urllib.error.HTTPError:
            return []

    def list_tags(self):
        page = self.refresh_csrf("/project")
        m = re.search(r'<meta\s+name="ol-tags"\s+(?:data-type="json"\s+)?content="([^"]*)"', page)
        if not m:
            return []
        import html
        return json.loads(html.unescape(m.group(1)))

    def upload_zip(self, zip_path, name, max_wait=1800):
        """Upload a project zip. Overleaf rate-limits this endpoint (HTTP 429), so on
        429 we wait (Retry-After header, else 60 s) and try again, for up to max_wait s."""
        waited = 0
        while True:
            try:
                # body schema is strict: only "name" (+ optional type/relativePath); CSRF goes in the header
                res = self.post_multipart("/project/new/upload", {"name": name},
                                          "qqfile", f"{name}.zip", zip_path)
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or waited >= max_wait:
                    raise
                try:
                    delay = int(e.headers.get("Retry-After") or 60)
                except ValueError:
                    delay = 60
                delay = max(5, min(delay, 300))
                log(f"  rate limited (HTTP 429); waiting {delay}s before retrying {name}")
                time.sleep(delay)
                waited += delay
        if not res or not res.get("success"):
            raise RuntimeError(f"upload rejected: {res}")
        return res["project_id"]

    def rename_project(self, pid, name):
        self.post_json(f"/project/{pid}/rename", {"newProjectName": name})

    def create_tag(self, name, color=None):
        payload = {"name": name}
        if color:
            payload["color"] = color
        res = self.post_json("/tag", payload)
        return res["_id"] if res and "_id" in res else res.get("id")

    def add_project_to_tag(self, tag_id, pid):
        self.post_json(f"/tag/{tag_id}/project/{pid}", {})

    EDITOR_SETTING_KEYS = (
        "mode", "editorTheme", "editorLightTheme", "editorDarkTheme", "overallTheme",
        "fontSize", "fontFamily", "lineHeight", "pdfViewer", "autoComplete",
        "autoPairDelimiters", "syntaxValidation", "mathPreview", "breadcrumbs",
        "editorTabs", "nonBlinkingCursor", "referencesSearchMode", "darkModePdf",
        "floatingMenu", "spellCheckLanguage",
    )

    def apply_user_settings(self, settings, first_name=None, last_name=None):
        payload = {k: v for k, v in (settings or {}).items() if k in self.EDITOR_SETTING_KEYS}
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if payload:
            self.post_json("/user/settings", payload)
        return payload

    def archive(self, pid):
        self.post_json(f"/project/{pid}/archive", {})

    def trash(self, pid):
        self.post_json(f"/project/{pid}/trash", {})


def main():
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("LOCAL_OVERLEAF_URL", "http://localhost"))
    ap.add_argument("--email", default=os.environ.get("LOCAL_OVERLEAF_EMAIL"), required="LOCAL_OVERLEAF_EMAIL" not in os.environ)
    ap.add_argument("--password", default=os.environ.get("LOCAL_OVERLEAF_PASSWORD"))
    ap.add_argument("--manifest", default=str(root / "migration" / "manifest.json"))
    ap.add_argument("--zips", default=str(root / "migration" / "zips"))
    ap.add_argument("--state", default=str(root / "migration" / "import-state.json"))
    ap.add_argument("--include-trashed", action="store_true", help="also import projects that were in Trash (they land in the local Trash)")
    ap.add_argument("--no-layout", action="store_true", help="only upload; skip tags/archive/trash")
    ap.add_argument("--no-settings", action="store_true", help="do not copy your name / editor settings from the manifest")
    args = ap.parse_args()
    if not args.password:
        import getpass
        args.password = getpass.getpass(f"Password for {args.email} on {args.url}: ")

    manifest = json.loads(Path(args.manifest).read_text())
    state_path = Path(args.state)
    state = json.loads(state_path.read_text()) if state_path.exists() else {"projects": {}, "tags": {}}

    def save_state():
        state_path.write_text(json.dumps(state, indent=2))

    ol = Local(args.url)
    ol.login(args.email, args.password)

    # ---- 1. upload every project ----
    ok = skipped = failed = 0
    for p in manifest["projects"]:
        old_id, name = p["id"], p["name"]
        if old_id in state["projects"]:
            log(f"already imported  {name}")
            skipped += 1
            continue
        if not p.get("zip"):
            log(f"no zip, skipping  {name}")
            skipped += 1
            continue
        if p.get("trashed") and not args.include_trashed:
            log(f"trashed, skipping {name}  (use --include-trashed)")
            skipped += 1
            continue
        zip_path = Path(args.zips) / p["zip"]
        if not zip_path.exists():
            log(f"MISSING zip       {name} -> {zip_path}")
            failed += 1
            continue
        try:
            log(f"uploading         {name} ({zip_path.stat().st_size} bytes)")
            new_id = ol.upload_zip(zip_path, name)
            # the upload endpoint may strip characters from the name; enforce the original
            try:
                ol.rename_project(new_id, name)
            except urllib.error.HTTPError:
                pass
            state["projects"][old_id] = {"new_id": new_id, "name": name}
            save_state()
            ok += 1
            log(f"  -> {args.url}/project/{new_id}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            log(f"  FAILED: {e}")
    log(f"uploads: {ok} new, {skipped} skipped, {failed} failed")

    if args.no_layout:
        return

    # ---- 2. tags (dashboard folders) ----
    existing = {t["name"]: (t.get("_id") or t.get("id")) for t in ol.list_tags()}
    for t in manifest.get("tags", []):
        tname = t["name"]
        tag_id = state["tags"].get(tname) or existing.get(tname)
        if not tag_id:
            tag_id = ol.create_tag(tname, t.get("color"))
            log(f"created tag       {tname}")
        state["tags"][tname] = tag_id
        save_state()
        for old_pid in t.get("project_ids", []):
            mapped = state["projects"].get(old_pid)
            if mapped:
                try:
                    ol.add_project_to_tag(tag_id, mapped["new_id"])
                except urllib.error.HTTPError as e:
                    log(f"  could not tag {mapped['name']} with {tname}: HTTP {e.code}")
        log(f"tag {tname}: applied to {sum(1 for x in t.get('project_ids', []) if x in state['projects'])} projects")

    # ---- 3. archived / trashed flags ----
    for p in manifest["projects"]:
        mapped = state["projects"].get(p["id"])
        if not mapped or mapped.get("flags_done"):
            continue
        try:
            if p.get("trashed"):
                ol.trash(mapped["new_id"]); log(f"trashed           {p['name']}")
            elif p.get("archived"):
                ol.archive(mapped["new_id"]); log(f"archived          {p['name']}")
            mapped["flags_done"] = True
            save_state()
        except urllib.error.HTTPError as e:
            log(f"  flag failed for {p['name']}: HTTP {e.code}")

    # ---- 4. your name + editor preferences (theme, font, keybindings, ...) ----
    if not args.no_settings and (manifest.get("user_settings") or manifest.get("user")):
        u = manifest.get("user") or {}
        try:
            applied = ol.apply_user_settings(manifest.get("user_settings"), u.get("first_name"), u.get("last_name"))
            log(f"applied user settings: {', '.join(sorted(applied)) or 'none'}")
        except urllib.error.HTTPError as e:
            log(f"  user settings failed: HTTP {e.code}")

    log("done. Open %s/project to see the result." % args.url)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
