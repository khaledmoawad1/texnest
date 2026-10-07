#!/usr/bin/env python3
"""Install TeXnest's branding into the web app: favicons, logo files, and every Overleaf brand image replaced."""
import glob
import os
import re
import shutil
import subprocess

SRC = "/tmp/branding"
PUB = "/overleaf/services/web/public"
MARK, MARK_DARK = f"{SRC}/texnest.svg", f"{SRC}/texnest-mark-dark.svg"
LOCKUP, LOCKUP_DARK = f"{SRC}/texnest-lockup.svg", f"{SRC}/texnest-lockup-dark.svg"

# TeXnest's own files, referenced by the theme and the navbar settings
for f in ("texnest.svg", "texnest-mark-dark.svg", "texnest-lockup.svg", "texnest-lockup-dark.svg"):
    shutil.copy(f"{SRC}/{f}", f"{PUB}/img/{f}")
for f in ("favicon.svg", "favicon.ico", "favicon-16x16.png", "favicon-32x32.png", "apple-touch-icon.png",
          "favicon-compiling.svg", "favicon-compiled.svg", "favicon-error.svg", "mask-favicon.svg"):
    shutil.copy(f"{SRC}/{f}", f"{PUB}/{f}")
shutil.copy(f"{SRC}/favicon.ico", f"{PUB}/sl-favicon.ico")          # legacy names still shipped by Overleaf
shutil.copy(f"{SRC}/mask-favicon.svg", f"{PUB}/sl-mask-favicon.svg")

# Browsers cache a favicon per URL and seldom refetch it, so the pages and the editor must point at new,
# TeXnest-specific names; the old names stay installed for anything else that asks for them.
ICONS = {"favicon.svg": "texnest-favicon.svg", "favicon-compiling.svg": "texnest-favicon-compiling.svg",
         "favicon-compiled.svg": "texnest-favicon-compiled.svg", "favicon-error.svg": "texnest-favicon-error.svg",
         "favicon-32x32.png": "texnest-favicon-32x32.png", "favicon-16x16.png": "texnest-favicon-16x16.png",
         "apple-touch-icon.png": "texnest-apple-touch-icon.png", "mask-favicon.svg": "texnest-mask-favicon.svg"}
for old, new in ICONS.items():
    shutil.copy(f"{SRC}/{old}", f"{PUB}/{new}")


def rewrite(path, pairs, required=True):
    """Replace quoted icon names in a template or bundle; fail the build if an expected name is missing."""
    s = open(path).read()
    for old, new in pairs:
        if old not in s:
            if required:
                raise SystemExit(f"{path} no longer contains {old!r}; update texlive-full/patches/brand-assets.py")
            continue
        s = s.replace(old, new)
    open(path, "w").write(s)


WEB = "/overleaf/services/web"
rewrite(f"{WEB}/app/views/_metadata.pug", [(f"'{o}'", f"'{n}'") for o, n in ICONS.items() if o != "favicon-compiling.svg"
                                              and o != "favicon-compiled.svg" and o != "favicon-error.svg"])
for path in glob.glob(f"{WEB}/app/views/**/*.js", recursive=True):   # precompiled views, when present
    rewrite(path, [(f"'{o}'", f"'{n}'") for o, n in ICONS.items()], required=False)
bundles = glob.glob(f"{PUB}/js/pages/ide-*.js")
if not bundles:
    raise SystemExit("editor bundle public/js/pages/ide-*.js not found")
for path in bundles:
    rewrite(path, [(f'"{o}"', f'"{n}"') for o, n in ICONS.items() if o.endswith(".svg") and o != "mask-favicon.svg"])
    # new content hash in the file name and in the asset manifest, so a cached copy of the bundle is never used
    d, b = os.path.split(path)
    new = re.sub(r"-[0-9a-f]{20}\.js$", "", b) + "-" + subprocess.run(["md5sum", path], capture_output=True, text=True).stdout[:20] + ".js"
    os.rename(path, os.path.join(d, new))
    rewrite(f"{PUB}/manifest.json", [(b, new)])
# Safari pinned-tab colour in the page templates
for path in glob.glob("/overleaf/services/web/app/views/layout/*.pug") + glob.glob("/overleaf/services/web/app/views/*.pug"):
    t = open(path).read()
    if 'mask-icon' in t and '#046530' in t:
        open(path, "w").write(t.replace('#046530', '#2F3E4E'))

# Overleaf's brand images (plain and webpack-hashed names) by stem: mark on light, mark on dark, lockup on light/dark
REPLACE = {"overleaf-o-dark": MARK, "overleaf-o": MARK, "overleaf-o-grey": MARK_DARK, "overleaf-o-white": MARK_DARK,
           "overleaf-white": LOCKUP_DARK, "overleaf-a-ds-solution-mallard-dark": LOCKUP_DARK,
           "overleaf-green": LOCKUP, "overleaf-black": LOCKUP, "overleaf": LOCKUP, "overleaf-logo": LOCKUP,
           "overleaf-a-ds-solution-mallard": LOCKUP}
count = 0
for path in glob.glob(f"{PUB}/img/ol-brand/*.svg") + glob.glob(f"{PUB}/images/*.svg"):
    name = os.path.basename(path)
    if not name.startswith("overleaf"):
        continue
    stem = re.sub(r"-[0-9a-f]{20}$", "", name[:-4])
    if stem not in REPLACE:
        raise SystemExit(f"no TeXnest replacement defined for {path}")
    shutil.copy(REPLACE[stem], path); count += 1

# PNG logos (e-mails, social preview) rendered from the lockup
def png(src, dest, width):
    subprocess.run(["inkscape", "-w", str(width), src, "-o", dest], check=True, capture_output=True)
png(LOCKUP, f"{PUB}/img/ol-brand/logo-horizontal.png", 400)
png(LOCKUP, f"{PUB}/img/ol-brand/email-logo@2x.png", 300)
png(MARK, f"{PUB}/img/ol-brand/overleaf_og_logo.png", 600)
# the e-mail footer tagline is Overleaf's; replace it with a transparent image of the same proportions
open("/tmp/blank.svg", "w").write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 904 50" width="904" height="50"/>')
png("/tmp/blank.svg", f"{PUB}/img/ol-brand/email-footer-tagline@2x.png", 904)
print(f"brand assets installed: {count} Overleaf images replaced")
