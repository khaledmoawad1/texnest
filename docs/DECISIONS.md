# Design notes and decisions

Technical background for maintainers. Users only need the README.

## Why the pieces are the way they are

**Overleaf Toolkit as a git submodule.** `overleaf-toolkit/` is the unmodified
upstream repository. Its `bin/*` scripts are the real commands; `./texnest`
only wraps them. The toolkit's `.gitignore` ignores `config/` and `data/`, so the
configuration lives in `./config/` and `./texnest` symlinks each file into
`overleaf-toolkit/config/` (those links are ignored by the toolkit, which keeps the
submodule clean).

**Secrets and personal values are not in git.** `config/variables.env` holds the
generic settings. `config/local.env` (git-ignored, generated on first run) holds
`OVERLEAF_INVITE_TOKEN_SECRET` plus any personal overrides (admin e-mail, site
URL, …). `config/docker-compose.override.yml` (a mechanism the toolkit supports)
loads both; values in `local.env` win because it is listed last.

**Full TeX Live baked into the image.** Overleaf Community Edition ships only
`scheme-basic` (≈150 packages, no biber, no fonts). Overleaf's sandboxed-compile
images are a Server Pro feature, so the documented CE route is used: install
`scheme-full` on top of the CE image and run the tag `<version>-with-texlive-full`
(the toolkit's version regex explicitly allows that suffix).
`texlive-full/Dockerfile` does this reproducibly, without docs/sources
(≈5 GB instead of ≈8 GB), with retries, from a pinned fast CTAN mirror
(`mirror.ctan.org` can redirect to very slow mirrors; override with `TL_MIRROR`).
Layers added later (ghostscript, shell escape) sit *after* the TeX Live layer so
that rebuilds reuse the cache.

**Unrestricted shell escape.** The Overleaf compiler service runs
`latexmk` without `-shell-escape`, so TeX Live's default *restricted* mode
applies: minted still works (its `latexminted` helper is allow-listed) but
pgfplots→gnuplot and the svg package (inkscape) fail. overleaf.com compiles with
full shell escape, so `shell_escape = t` is appended to the TeX Live root
`texmf.cnf`. Consequence: anyone who can compile can run commands inside the
`sharelatex` container. Only give accounts to people you trust (Overleaf says the
same about Community Edition in general).

**ghostscript + ImageMagick.** Needed by epstopdf for EPS figures (many journal
templates ship EPS logos) and by some packages via shell escape.

**MongoDB 8.2.x, not 8.0.** MongoDB 8.0.x and 8.3.x images refuse to start on
Linux kernels ≥ 6.19 (TCMalloc rseq incompatibility, MongoDB tickets
SERVER-121912 / SERVER-125742; the guard is lifted only for ≥ 7.0.14). 8.2.12
starts everywhere and was load-tested. Overleaf 6.x requires MongoDB ≥ 8.0.

**Docker legacy builder.** Some distro Docker packages lack buildx; the Dockerfile
and `./texnest build-texlive` work with both (no `--progress` flag).

## Overleaf API facts the scripts rely on

* Session cookie: `overleaf_session2` on overleaf.com, `overleaf.sid` on CE.
  overleaf.com's login form has a CAPTCHA, hence the cookie-based exporter.
* Dashboard data is embedded in `/project` as `<meta name="ol-…">` tags:
  `ol-prefetchedProjectsBlob` (projects), `ol-tags`, `ol-user`, `ol-userSettings`,
  `ol-csrfToken`. Fallback listing: `POST /api/project` with
  `{filters:{}, page:{size,lastId}, sort:{by,order}}`.
* Zip of a project: `GET /project/<id>/download/zip` (works for shared projects too).
* Upload: `POST /project/new/upload`, multipart field `qqfile`, body has only
  `name` (strict schema). Rate limit: **20 project uploads per 60 s** → the
  importer waits on HTTP 429.
* Tags: `POST /tag {name,color}`, `POST /tag/<tag>/project/<project>`;
  flags: `POST /project/<id>/archive|trash`; settings: `POST /user/settings`;
  compiler: `POST /project/<id>/settings {compiler}`; compile:
  `POST /project/<id>/compile`.
* CSRF token goes in the `x-csrf-token` header only — several endpoints have
  strict body schemas that reject an `_csrf` field.
* Application logs are files in `/var/log/overleaf/` (mounted to
  `overleaf-toolkit/data/logs/`), not `docker logs`. Password-reset links are
  written to `web.log` because no mail is sent.

## Branding

Overleaf is a trademark of Overleaf (Digital Science). This project is a
packaging of the AGPL-licensed Overleaf Community Edition and is not affiliated
with or endorsed by Overleaf. The service is therefore branded **TeXnest**
(`OVERLEAF_APP_NAME`, `OVERLEAF_HEADER_IMAGE_URL`, footer links and favicons in
`config/` + `branding/`), and the footer links to the Overleaf source as the AGPL
requires for a network service.
