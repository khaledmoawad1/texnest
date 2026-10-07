# Overleaf Community Edition plus the complete TeX Live and the tools overleaf.com's compiler has.
# Built by `./texnest build-texlive`; change BASE_VERSION on an Overleaf upgrade.
ARG BASE_VERSION=6.3.0
FROM sharelatex/sharelatex:${BASE_VERSION}

# System fonts for XeLaTeX/LuaLaTeX, Pygments for minted, Inkscape for svg, gnuplot for pgfplots.
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

# Complete TeX Live without docs/sources; the install is retried because one mirror error would discard the layer.
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

# Unrestricted shell escape like overleaf.com, so pgfplots+gnuplot and svg+inkscape work (Overleaf's compiler does not pass -shell-escape).
RUN TL_ROOT="$(ls -d /usr/local/texlive/20*)" \
 && printf '%s\n' '% enable unrestricted shell escape (overleaf.com behaviour)' 'shell_escape = t' >> "$TL_ROOT/texmf.cnf" \
 && [ "$(kpsewhich -var-value shell_escape)" = "t" ]

# Ghostscript for EPS figures (epstopdf) and ImageMagick, kept in their own layer so the TeX Live layer stays cached.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ghostscript imagemagick \
 && rm -rf /var/lib/apt/lists/*

# Fail the build if any required tool is missing.
RUN set -e; for b in pdflatex xelatex lualatex latexmk biber bibtex makeindex \
      makeglossaries xindy pygmentize inkscape gnuplot gs convert; do \
      command -v "$b" >/dev/null || { echo "MISSING: $b"; exit 1; }; done \
 && [ "$(kpsewhich -var-value shell_escape)" = "t" ] \
 && tlmgr list --only-installed | grep -c '^i ' \
 && fc-list : family | sort -u | wc -l
