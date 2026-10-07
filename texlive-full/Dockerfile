# Overleaf Community Edition + complete TeX Live + the extra tools overleaf.com's
# compile environment has (biber, pygments for minted, inkscape for svg,
# gnuplot for pgfplots, common system fonts for XeLaTeX/LuaLaTeX).
#
# Build (from the repo root):
#   docker build -t sharelatex/sharelatex:6.3.0-with-texlive-full texlive-full/
# then set overleaf-toolkit/config/version to 6.3.0-with-texlive-full and run bin/up -d.
#
# On an Overleaf upgrade: change BASE_VERSION, rebuild, retag, update config/version.
ARG BASE_VERSION=6.3.0
FROM sharelatex/sharelatex:${BASE_VERSION}

# --- system extras ---------------------------------------------------------
# fonts-liberation       : metric-compatible Arial / Times New Roman / Courier New
# fonts-crosextra-*      : metric-compatible Calibri (Carlito) / Cambria (Caladea)
# fonts-dejavu, noto, freefont : broad Unicode coverage for XeLaTeX / LuaLaTeX
# python3-pygments       : pygmentize, required by the minted package
# inkscape               : required by the svg package (\includesvg)
# gnuplot-nox            : gnuplot back-end for pgfplots / gnuplottex
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      fontconfig \
      fonts-liberation fonts-liberation2 fonts-crosextra-carlito fonts-crosextra-caladea \
      fonts-dejavu fonts-noto-core fonts-freefont-ttf fonts-lmodern \
      python3-pygments \
      inkscape \
      gnuplot-nox \
 && rm -rf /var/lib/apt/lists/* \
 && fc-cache -f

# --- complete TeX Live -----------------------------------------------------
# Docs and sources are skipped (as on overleaf.com) to keep the image ~5 GB
# instead of ~8 GB. The install is retried because a single mirror hiccup
# would otherwise discard the whole layer; already-installed packages are
# skipped on retry.
ARG TL_MIRROR=https://mirror.dogado.de/tex-archive/systems/texlive/tlnet
RUN tlmgr option repository "${TL_MIRROR}" \
 && tlmgr option docfiles 0 \
 && tlmgr option srcfiles 0 \
 && tlmgr option autobackup 0 \
 && tlmgr update --self \
 && tlmgr update --all \
 && for attempt in 1 2 3 4 5; do \
        echo "=== tlmgr install scheme-full, attempt ${attempt} ==="; \
        tlmgr install scheme-full && break; \
        sleep 20; \
    done \
 && tlmgr install scheme-full \
 && tlmgr path add \
 && rm -rf /usr/local/texlive/*/tlpkg/backups/* /tmp/* \
 && (luaotfload-tool -u -f >/dev/null 2>&1 || true) \
 && (mtxrun --generate >/dev/null 2>&1 || true)

# --- unrestricted shell escape, as on overleaf.com ------------------------
# The Overleaf compiler service runs latexmk without -shell-escape, so TeX Live's
# default "restricted" mode (shell_escape = p) applies: only allow-listed helpers
# (latexminted, bibtex, kpsewhich, ...) may run. overleaf.com enables full shell
# escape, which pgfplots+gnuplot, the svg package (inkscape), gnuplottex, epstopdf
# of arbitrary files etc. need. Set it in the installation-root texmf.cnf, which
# TeX Live reads as the local override of texmf-dist/web2c/texmf.cnf.
# (Verified 2026-10-05: pgfplots+gnuplot, svg+inkscape and minted all compile.)
RUN TL_ROOT="$(ls -d /usr/local/texlive/20*)" \
 && printf '%s\n' '% enable unrestricted shell escape (overleaf.com behaviour)' 'shell_escape = t' >> "$TL_ROOT/texmf.cnf" \
 && [ "$(kpsewhich -var-value shell_escape)" = "t" ]

# --- converters found missing when compiling real projects (2026-10-05) ------
# ghostscript : required by epstopdf/repstopdf for EPS figures (MDPI template logo
#               failed with "logo-mdpi-eps-converted-to.pdf not found")
# imagemagick : `convert`, used by some packages/templates via shell escape
# Kept as a separate layer so the big TeX Live layer above stays cached.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ghostscript imagemagick \
 && rm -rf /var/lib/apt/lists/*

# sanity check: every tool overleaf.com projects commonly rely on must exist
RUN set -e; for b in pdflatex xelatex lualatex latexmk biber bibtex makeindex \
      makeglossaries xindy pygmentize inkscape gnuplot gs convert; do \
      command -v "$b" >/dev/null || { echo "MISSING: $b"; exit 1; }; done \
 && [ "$(kpsewhich -var-value shell_escape)" = "t" ] \
 && tlmgr list --only-installed | grep -c '^i ' \
 && fc-list : family | sort -u | wc -l
