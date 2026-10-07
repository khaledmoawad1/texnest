#!/usr/bin/env python3
"""
Export ALL of your projects from overleaf.com (source zips + dashboard layout).

What it saves (into --out, default ./migration):
  zips/<project_id>.zip          one zip per project (every file: .tex, .bib, images, ...)
  manifest.json                  everything needed to rebuild the dashboard locally:
                                 project names, tags (the dashboard "folders"),
                                 archived / trashed flags, owner / access level, last-updated,
                                 your name and your editor settings (theme, font, keybindings,
                                 PDF viewer, spell-check language, ...)

How to authenticate (overleaf.com has a CAPTCHA on the login form, so we reuse
your browser session instead of a password):
  1. Log in to https://www.overleaf.com in your browser.
  2. Open DevTools -> Application (Chrome) / Storage (Firefox) -> Cookies
     -> https://www.overleaf.com -> copy the VALUE of the cookie named
     "overleaf_session2".
  3. Run:
       python3 scripts/export_overleaf_projects.py --cookie 'PASTE_VALUE_HERE'
     or put it in the environment:  OVERLEAF_SESSION=... python3 scripts/export_overleaf_projects.py

Only the Python standard library is used, so it runs anywhere.
Re-running is safe: zips that already exist with a non-zero size are skipped
unless --force is given.
"""
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

BASE = "https://www.overleaf.com"
UA = "Mozilla/5.0 (X11; Linux x86_64) overleaf-local-migration/1.0"


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


class Client:
    def __init__(self, session_cookie, base=BASE, cookie_name="overleaf_session2"):
        self.base = base
        self.cookie_name = cookie_name
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.session_cookie = session_cookie.strip().strip('"').strip("'")
        self.csrf = None

    def _headers(self, extra=None):
        h = {
            "User-Agent": UA,
            "Cookie": f"{self.cookie_name}={self.session_cookie}",
            "Accept": "*/*",
        }
        if self.csrf:
            h["x-csrf-token"] = self.csrf
        if extra:
            h.update(extra)
        return h

    def get(self, path, headers=None, timeout=120):
        req = urllib.request.Request(self.base + path, headers=self._headers(headers))
        return self.opener.open(req, timeout=timeout)

    def post_json(self, path, payload, timeout=120):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method="POST",
            headers=self._headers({"Content-Type": "application/json", "Accept": "application/json"}),
        )
        with self.opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "null")


def extract_meta(page, name):
    """Return the decoded `content` of <meta name="..." content="..."> or None."""
    m = re.search(
        r'<meta\s+name="%s"\s+(?:data-type="json"\s+)?content="([^"]*)"' % re.escape(name), page
    )
    if not m:
        m = re.search(
            r'<meta\s+(?:data-type="json"\s+)?content="([^"]*)"\s+name="%s"' % re.escape(name), page
        )
    return html.unescape(m.group(1)) if m else None


def fetch_dashboard(client):
    """Return (projects, tags, user) from the overleaf.com project dashboard."""
    with client.get("/project", headers={"Accept": "text/html"}) as r:
        final_url = r.geturl()
        page = r.read().decode("utf-8", "replace")
    if "/login" in final_url or 'name="ol-csrfToken"' not in page:
        sys.exit(
            "ERROR: not logged in. The overleaf_session2 cookie is missing/expired. "
            "Log in again in the browser and copy a fresh cookie value."
        )
    client.csrf = extract_meta(page, "ol-csrfToken")
    user = None
    raw_user = extract_meta(page, "ol-user")
    if raw_user:
        try:
            user = json.loads(raw_user)
        except json.JSONDecodeError:
            pass

    projects, tags = [], []
    raw = extract_meta(page, "ol-prefetchedProjectsBlob")
    if raw:
        blob = json.loads(raw)
        projects = blob.get("projects", [])
        log(f"dashboard prefetched blob: {len(projects)} projects (totalSize={blob.get('totalSize')})")
        # The prefetched blob may be capped; fall back to the paginated API for the rest.
        if blob.get("totalSize") and blob["totalSize"] > len(projects):
            projects = fetch_projects_api(client) or projects
    else:
        log("no prefetched blob in dashboard HTML, using /api/project")
        projects = fetch_projects_api(client)

    raw_tags = extract_meta(page, "ol-tags")
    if raw_tags:
        tags = json.loads(raw_tags)
    log(f"found {len(projects)} projects and {len(tags)} tags (dashboard folders)")

    # Per-user editor preferences (theme, font, keybindings, PDF viewer, ...) so the
    # local instance can look exactly like overleaf.com for you.
    settings = None
    raw_settings = extract_meta(page, "ol-userSettings")
    if raw_settings:
        try:
            settings = json.loads(raw_settings)
        except json.JSONDecodeError:
            pass
    profile = None
    try:
        with client.get("/user/settings", headers={"Accept": "text/html"}) as r:
            sp = r.read().decode("utf-8", "replace")
        raw_profile = extract_meta(sp, "ol-user")
        if raw_profile:
            profile = json.loads(raw_profile)
    except Exception as e:  # noqa: BLE001 - optional nicety
        log(f"could not read /user/settings profile page: {e}")
    return projects, tags, user, settings, profile


def fetch_projects_api(client):
    """Paginated project list used by the React dashboard.
    Body schema (web/app/src/Features/Project/ProjectListController.mjs):
      {filters: {}, sort: {by, order}, page: {size?: int, lastId?: objectId}}"""
    projects, last_id = [], None
    while True:
        page = {"size": 500}
        if last_id:
            page["lastId"] = last_id
        try:
            res = client.post_json(
                "/api/project",
                {"filters": {}, "page": page, "sort": {"by": "lastUpdated", "order": "desc"}},
            )
        except urllib.error.HTTPError as e:
            log(f"/api/project failed with HTTP {e.code}; giving up on API listing")
            return projects
        batch = res.get("projects", []) if isinstance(res, dict) else []
        projects.extend(batch)
        total = res.get("totalSize", len(projects)) if isinstance(res, dict) else len(projects)
        if not batch or len(projects) >= total:
            break
        last_id = batch[-1].get("id") or batch[-1].get("_id")
        if not last_id:
            break
    return projects


def safe_name(name):
    return re.sub(r"[^\w.\- ]+", "_", name).strip() or "untitled"


def download_zip(client, pid, dest, retries=3):
    for attempt in range(1, retries + 1):
        try:
            with client.get(f"/project/{pid}/download/zip", timeout=600) as r:
                tmp = dest.with_suffix(".part")
                with open(tmp, "wb") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                tmp.replace(dest)
                return dest.stat().st_size
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            log(f"  attempt {attempt}/{retries} failed for {pid}: {e}")
            time.sleep(3 * attempt)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cookie", default=os.environ.get("OVERLEAF_SESSION"), help="value of overleaf_session2 cookie")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "migration"))
    ap.add_argument("--force", action="store_true", help="re-download zips that already exist")
    ap.add_argument("--include-trashed", action="store_true", help="also download projects in Trash")
    ap.add_argument("--only-owned", action="store_true", help="skip projects shared with you by others")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds to wait between downloads (be polite)")
    ap.add_argument("--base", default=BASE, help="Overleaf instance to export from (default: overleaf.com; "
                    "use e.g. http://localhost to export from a self-hosted instance)")
    ap.add_argument("--cookie-name", default="overleaf_session2",
                    help="session cookie name (overleaf.com: overleaf_session2; Community Edition: overleaf.sid)")
    args = ap.parse_args()
    if not args.cookie:
        ap.error("--cookie (or OVERLEAF_SESSION env var) is required; see --help")

    out = Path(args.out)
    zips = out / "zips"
    zips.mkdir(parents=True, exist_ok=True)

    client = Client(args.cookie, base=args.base.rstrip("/"), cookie_name=args.cookie_name)
    projects, tags, user, settings, profile = fetch_dashboard(client)
    if profile:
        user = {**(user or {}), **{k: profile.get(k) for k in ("first_name", "last_name", "email") if profile.get(k)}}
    # spell-check language lives under user.ace (dashboard or profile page), not in ol-userSettings
    for src in (user, profile):
        ace = (src or {}).get("ace") or {}
        if settings is not None and ace.get("spellCheckLanguage") and not settings.get("spellCheckLanguage"):
            settings["spellCheckLanguage"] = ace["spellCheckLanguage"]

    manifest = {
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": client.base,
        "user": {"id": user.get("id") or user.get("_id"), "email": user.get("email"),
                 "first_name": user.get("first_name"), "last_name": user.get("last_name")} if user else None,
        "user_settings": settings,
        "tags": [{"id": t.get("_id") or t.get("id"), "name": t.get("name"), "color": t.get("color"),
                  "project_ids": t.get("project_ids", [])} for t in tags],
        "projects": [],
    }

    done = skipped = failed = 0
    for p in projects:
        pid = p.get("id") or p.get("_id")
        name = p.get("name", "untitled")
        archived = bool(p.get("archived"))
        trashed = bool(p.get("trashed"))
        access = p.get("accessLevel")
        owner = p.get("owner") or {}
        entry = {
            "id": pid,
            "name": name,
            "archived": archived,
            "trashed": trashed,
            "accessLevel": access,
            "owner_email": owner.get("email"),
            "owner_id": owner.get("id") or owner.get("_id"),
            "lastUpdated": p.get("lastUpdated"),
            "zip": None,
        }
        manifest["projects"].append(entry)

        if trashed and not args.include_trashed:
            log(f"skip (trashed)  {name} [{pid}]")
            skipped += 1
            continue
        if args.only_owned and access != "owner":
            log(f"skip (shared)   {name} [{pid}]")
            skipped += 1
            continue

        dest = zips / f"{pid}.zip"
        if dest.exists() and dest.stat().st_size > 0 and not args.force:
            entry["zip"] = dest.name
            log(f"have            {name} [{pid}] ({dest.stat().st_size} bytes)")
            done += 1
            continue

        log(f"download        {name} [{pid}]")
        size = download_zip(client, pid, dest)
        if size:
            entry["zip"] = dest.name
            log(f"  ok {size} bytes")
            done += 1
        else:
            log(f"  FAILED {name}")
            failed += 1
        time.sleep(args.delay)

        # Write the manifest after every project so a crash loses nothing.
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    log(f"finished: {done} zips ready, {skipped} skipped, {failed} failed -> {out}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
