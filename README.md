<p align="center"><img src="branding/texnest-512.png" width="96" alt="TeXnest"></p>

# TeXnest — run Overleaf locally on your own device

TeXnest is a **self-hosted LaTeX server**. It gives you the Overleaf editor, dashboard and compiler on your own computer: the same workflow you know from overleaf.com, with the complete TeX Live, no project or collaborator limits, and your files kept on your device. It works offline, starts with one command, and can import everything from your overleaf.com account.

## Why TeXnest

- **Self-hosted.** Everything runs on your machine in Docker. Your documents never leave it.
- **Complete TeX Live.** Every CTAN package, biber, minted, TikZ/pgfplots with gnuplot, the svg package with Inkscape, EPS figures, system fonts for XeLaTeX and LuaLaTeX, shell escape. What compiles on overleaf.com compiles here.
- **Your projects, moved in two commands.** Projects, tags, archived state, your name and your editor settings come over from overleaf.com.
- **One command for everything.** Install, start, backup, restore, update, users and a compile self-test through `./texnest`.
- **The real Overleaf.** TeXnest packages the open-source Overleaf Community Edition, so the editor, project history, sharing and dashboard are the ones you already use.

## Requirements

- Linux with Docker 24+ and the compose plugin, your user in the `docker` group (`docker ps` works without sudo). macOS with Docker Desktop should work as well.
- `git` and `python3` (3.8+, standard library only).
- About 15 GB of free disk (the image is 8 GB) and 4 GB of RAM.

## Install

```bash
git clone --recurse-submodules https://github.com/khaledmoawad1/texnest.git
cd texnest
./texnest install                  # builds the TeX Live image and starts TeXnest
./texnest admin you@example.com    # creates your account and prints a link to set the password
```

Open the printed link, choose a password, and go to **<http://localhost:8090>**. TeXnest starts again by itself after a reboot.

TeXnest comes with a local mailbox at **<http://localhost:8091>**: every e-mail it sends (password resets, project invitations) lands there, so "Forgot your password?" works without any mail account. The footer links to it.

The same thing in steps: `./texnest bootstrap`, `./texnest build-texlive`, `./texnest up`.

## Everyday use

| Command | What it does |
|---|---|
| `./texnest status` | shows the containers (sharelatex, mongo, redis, mail) and the URL |
| `./texnest up` / `stop` / `restart` | start (also applies config changes), stop, restart |
| `./texnest logs` | follows the web log; `./texnest logs clsi` follows the compiler |
| `./texnest backup` | full backup into `backups/<date>/` |
| `./texnest restore backups/<date>` | brings a backup back |
| `./texnest user someone@example.com` | adds a user (create accounts for people you trust); `admin` instead of `user` makes an administrator |
| `./texnest reset-password you@example.com` | prints a link to set a new password (the same link also arrives in the local mailbox) |
| `./texnest selftest` | compiles three test projects (biber, minted, svg, fonts, beamer) |
| `./texnest theme '#2F3E4E' '#D9A21B'` | recolors the interface from a primary and an accent color |
| `./texnest help` | lists all commands |

Inside TeXnest it is Overleaf: *New project* (blank, example or *Upload project* from a zip), *Recompile*, *Menu* for the compiler, main document and PDF download, *Share*, *History*, and tags in the left sidebar.

## Move your projects from overleaf.com

1. Log in to overleaf.com in your browser. Open the developer tools (F12) → *Application* (Chrome, Edge) or *Storage* (Firefox) → *Cookies* → `https://www.overleaf.com` → copy the **value** of the cookie `overleaf_session2`.
2. Download everything (one zip per project plus `migration/manifest.json` with names, tags, flags and settings):

   ```bash
   python3 scripts/export_overleaf_projects.py --cookie 'PASTE_VALUE'
   ```

   Add `--include-trashed` to take the Trash as well. Running it again only fetches what is new.
3. Import into TeXnest:

   ```bash
   python3 scripts/import_projects.py --email you@example.com
   ```

   Every project is uploaded and your tags, archived state, name and editor preferences are recreated. About 200 projects take ten minutes. Running it again never creates duplicates.
4. Open <http://localhost:8090/project>. For a project that used XeLaTeX or LuaLaTeX, pick that compiler once in its *Menu*.

## Backup and restore

`./texnest backup` writes `backups/texnest-backup-<date>/` with the database, all project files and history, and your configuration. Keep a copy somewhere safe. `./texnest restore <folder>` brings it back, also on a new machine after `./texnest install`.

## Update

```bash
./texnest backup
cd overleaf-toolkit && bin/upgrade && cd ..     # new toolkit and Overleaf version
./texnest build-texlive && ./texnest up && ./texnest selftest
```

Release notes: <https://github.com/overleaf/overleaf/wiki/Release-Notes-6.x>.

## Configuration

Settings live in `config/`; personal values go in `config/local.env`, which is created on first run and never committed, and override `config/variables.env`. Run `./texnest up` after a change.

- **Port**: `OVERLEAF_PORT` in `config/overleaf.rc`, plus `OVERLEAF_SITE_URL=http://localhost:<port>` in `local.env`.
- **Name, logo and colors**: `OVERLEAF_APP_NAME` and `OVERLEAF_NAV_TITLE` in `variables.env`; the files in `branding/`; `./texnest theme '#PRIMARY' '#ACCENT'` recolors the interface.
- **Other devices on your network**: `OVERLEAF_LISTEN_IP=0.0.0.0` in `overleaf.rc` and `OVERLEAF_SITE_URL=http://<your-ip>:8090` in `local.env`.
- **E-mail**: by default all e-mail goes to the local mailbox (<http://localhost:8091>). To send real e-mail instead, put your SMTP settings in `local.env` (`config/local.env.example` shows a Gmail example).
- **Extra packages or tools**: add them to `texlive-full/Dockerfile`, then `./texnest build-texlive && ./texnest up`.

## License and credits

TeXnest is released under the **GNU AGPL-3.0** (see `LICENSE`), the same license as [Overleaf Community Edition](https://github.com/overleaf/overleaf) and the [Overleaf Toolkit](https://github.com/overleaf/toolkit) it is built on. TeX Live, the fonts and the tools inside the image keep their own free licenses. TeXnest is an independent project and is not affiliated with or endorsed by Overleaf; Overleaf is a trademark of Overleaf.
