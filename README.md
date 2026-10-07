<p align="center"><img src="branding/texnest-512.png" width="96" alt="TeXnest logo"></p>

# TeXnest — host your own Overleaf alternative

TeXnest runs the open-source **Overleaf Community Edition** on your own machine
with one command, and adds what the plain edition is missing:

- the **complete TeX Live** (every CTAN package), biber, minted, TikZ/pgfplots
  with gnuplot, the svg package with Inkscape, EPS figures, system fonts for
  XeLaTeX/LuaLaTeX, shell escape — so projects that compile on overleaf.com
  compile here;
- scripts that **move all your overleaf.com projects** (with tags, archived
  state, your name and editor settings) to your instance in two commands;
- backup, restore, upgrade and a compile self-test, all through `./texnest`.

Same editor, same project dashboard, same history. Your files never leave your
computer. Works offline.

> TeXnest is a packaging of Overleaf Community Edition (AGPL-3.0). It is not
> affiliated with or endorsed by Overleaf. "Overleaf" is a trademark of Overleaf.

## Requirements

- Linux (tested on Ubuntu 24.04). macOS with Docker Desktop should work too.
- Docker 24+ with the compose plugin, your user in the `docker` group
  (`docker ps` works without sudo).
- `git`, `python3` (3.8+, standard library only), ~15 GB of free disk
  (the image is ~8 GB), 4 GB RAM.
- Port 80 free (changeable, see *Customize*).

## Install

```bash
git clone --recurse-submodules https://github.com/khaledmoawad1/texnest.git
cd texnest
./texnest install        # builds the TeX Live image (~30 min, downloads ~3 GB) and starts everything
./texnest admin you@example.com   # creates your admin account and prints a link to set the password
```

Open the printed link, set your password, then go to <http://localhost>.
That's it. TeXnest restarts by itself after a reboot.

Step by step, the same thing is: `./texnest bootstrap` (fetch the Overleaf
toolkit, link the config), `./texnest build-texlive`, `./texnest up`.

## Everyday commands

| | |
|---|---|
| `./texnest status` | is it running? (three containers: sharelatex, mongo, redis) |
| `./texnest up` / `stop` / `restart` | start (also applies config changes) / stop / restart |
| `./texnest logs` | follow the web log (`./texnest logs clsi` for the compiler) |
| `./texnest backup` | full backup into `backups/<date>/` (database + all project files + config) |
| `./texnest restore backups/<date>` | replace everything with that backup |
| `./texnest user someone@example.com` | add a user (`admin` instead of `user` for an administrator) |
| `./texnest selftest` | compile three test projects (biber, minted, svg, fonts, beamer); exit 0 = all good |
| `./texnest doctor` | the toolkit's self-check |
| `./texnest shell` | root shell inside the Overleaf container |
| `./texnest help` | all commands |

Using it is just Overleaf: *New project* (blank, example or *Upload project* from a
zip), *Recompile*, *Menu* → compiler / main document / download PDF, *Share*,
*History*, tags in the left sidebar.

## Bring your projects from overleaf.com

overleaf.com puts a CAPTCHA on its login page, so the exporter reuses your browser
session instead of asking for a password.

1. Log in to overleaf.com in your browser. Open the developer tools (F12) →
   *Application* (Chrome/Edge) or *Storage* (Firefox) → *Cookies* →
   `https://www.overleaf.com` → copy the **value** of the cookie `overleaf_session2`.
2. Download everything (one zip per project, plus `migration/manifest.json` with
   names, tags, archived/trashed flags, your name and editor settings):

   ```bash
   python3 scripts/export_overleaf_projects.py --cookie 'PASTE_VALUE'
   ```

   Add `--include-trashed` to take the Trash too. Re-running skips what you already have.
3. Import into TeXnest (asks for your TeXnest password; or set
   `LOCAL_OVERLEAF_EMAIL` / `LOCAL_OVERLEAF_PASSWORD` in the environment):

   ```bash
   python3 scripts/import_projects.py --email you@example.com
   ```

   It uploads every project, recreates your tags, archived/trashed state, your
   name and editor preferences. Overleaf allows 20 uploads per minute, so ~200
   projects take about 10 minutes. Re-running never creates duplicates.
4. Open <http://localhost/project>. If a project used XeLaTeX or LuaLaTeX on
   overleaf.com, set that once in its *Menu* (the zip doesn't carry that setting).

Not included in a zip export: project history, chat and comments.

## Backup and restore

`./texnest backup` writes `backups/texnest-backup-<date>/` with a MongoDB dump,
an archive of all project files and history, and your config. Copy that folder
somewhere safe. `./texnest restore <folder>` puts it back (also on a new machine,
after `./texnest install`).

## Update

```bash
./texnest backup
cd overleaf-toolkit && bin/upgrade && cd ..   # new toolkit + new Overleaf version number
./texnest build-texlive && ./texnest up && ./texnest selftest
```

Read the release notes first: <https://github.com/overleaf/overleaf/wiki/Release-Notes-6.x>.

## Customize

Everything is in `config/`. Put personal values in `config/local.env` (created on
first run, never committed); it overrides `config/variables.env`. After any
change run `./texnest up`.

| I want to… | Do |
|---|---|
| use my own name and logo | `OVERLEAF_APP_NAME`, `OVERLEAF_NAV_TITLE`, `OVERLEAF_HEADER_IMAGE_URL` in `variables.env`; replace the files in `branding/` (they are mounted into the app) |
| another port | `OVERLEAF_PORT=8080` in `config/overleaf.rc`, `OVERLEAF_SITE_URL=http://localhost:8080` in `local.env` |
| reach it from other devices on my network | `OVERLEAF_LISTEN_IP=0.0.0.0` in `overleaf.rc`, `OVERLEAF_SITE_URL=http://<your-ip>` in `local.env`. Use the toolkit's TLS proxy (`overleaf-toolkit/doc/tls-proxy.md`) for HTTPS |
| longer compiles (default 3 min, max 10) | `./texnest shell`, then `cd /overleaf/services/web && node modules/server-ce-scripts/scripts/change-compile-timeout.mjs --user-id=<id> --compile-timeout=600` (user ids are at <http://localhost/admin/user>) |
| send e-mails (invites, password resets) | fill the `OVERLEAF_EMAIL_SMTP_*` lines in `variables.env`. Without SMTP, links are printed by `./texnest user` or written to `overleaf-toolkit/data/logs/web.log` |
| an extra LaTeX package or tool | add it to `texlive-full/Dockerfile`, then `./texnest build-texlive && ./texnest up` (temporary: `./texnest shell`, `tlmgr install <pkg> && tlmgr path add`) |

## Troubleshooting

- **`mongo` keeps restarting with "kernel versions 6.19 and newer"** — MongoDB
  8.0/8.3 images refuse new kernels; keep `MONGO_VERSION=8.2.12` (the default here).
- **Port 80 already in use** — change the port (see *Customize*).
- **A package is "not found"** — run `./texnest selftest`; if it passes, the project
  needs a package outside TeX Live (add it to the Dockerfile).
- **Forgot the password** — <http://localhost/user/password/reset>, then
  `docker exec sharelatex grep -o 'http://localhost/user/password/set?[^"\\ ]*' /var/log/overleaf/web.log | tail -1`
  and open that link.
- **`docker build: unknown flag --progress`** — harmless; the scripts don't use it.
- Anything else: `./texnest doctor`, `./texnest logs`, and
  [docs/DECISIONS.md](docs/DECISIONS.md) for how the pieces fit together.

## What's different from overleaf.com

Community Edition is the same editor and dashboard code with the paid features
removed: no track changes / comments, no templates gallery (upload any template
zip instead), no Git/GitHub/Dropbox/Zotero sync, no AI tools, one TeX Live
version (2026), sharing only with accounts on your instance.

**Security:** compiles are not sandboxed and shell escape is enabled (as on
overleaf.com), so anyone with an account can run commands inside the Overleaf
container. Only create accounts for people you trust, and don't expose TeXnest to
the internet without the TLS proxy and a good reason.

## License

TeXnest's own files are released under the **GNU AGPL-3.0** (see `LICENSE`), the
same license as [Overleaf Community Edition](https://github.com/overleaf/overleaf)
and the [Overleaf Toolkit](https://github.com/overleaf/toolkit) it is built on.
TeX Live, the fonts and the tools in the image keep their own free licenses.
