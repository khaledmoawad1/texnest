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
for f in ("favicon.svg", "favicon.ico", "favicon-16x16.png", "favicon-32x32.png", "apple-touch-icon.png"):
    shutil.copy(f"{SRC}/{f}", f"{PUB}/{f}")

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
