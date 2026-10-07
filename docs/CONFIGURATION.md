# Configuration and troubleshooting

## Settings

Settings live in `config/`. Personal values belong in `config/local.env` (created on first run, never committed); it overrides `config/variables.env`. Run `./texnest up` after a change.

| Goal | Setting |
|---|---|
| Another port | `OVERLEAF_PORT` in `config/overleaf.rc` and `OVERLEAF_SITE_URL=http://localhost:<port>` in `local.env` |
| Your own name and logo | `OVERLEAF_APP_NAME`, `OVERLEAF_NAV_TITLE`, `OVERLEAF_HEADER_IMAGE_URL` in `variables.env`; replace the files in `branding/` |
| Use it from other devices on your network | `OVERLEAF_LISTEN_IP=0.0.0.0` in `overleaf.rc` and `OVERLEAF_SITE_URL=http://<your-ip>:8090` in `local.env`; the toolkit's TLS proxy adds HTTPS (`overleaf-toolkit/doc/tls-proxy.md`) |
| Longer compiles (default 3 min, up to 10) | `./texnest shell`, then `cd /overleaf/services/web && node modules/server-ce-scripts/scripts/change-compile-timeout.mjs --user-id=<id> --compile-timeout=600`; user ids are listed at `/admin/user` |
| E-mail for invites and password resets | fill the `OVERLEAF_EMAIL_SMTP_*` lines in `variables.env`; without SMTP the links are printed by `./texnest user` or written to `overleaf-toolkit/data/logs/web.log` |
| Extra packages or tools in the image | add them to `texlive-full/Dockerfile`, then `./texnest build-texlive && ./texnest up` |

## Troubleshooting

- **`mongo` restarts with "kernel versions 6.19 and newer"**: keep `MONGO_VERSION=8.2.12` in `config/overleaf.rc` (the default); MongoDB 8.0 and 8.3 images refuse new kernels.
- **Port 8090 is taken**: change the port as described above.
- **Forgot the password**: open `/user/password/reset`, submit the e-mail, then run `docker exec sharelatex grep -o 'http://[^"\\ ]*/user/password/set?[^"\\ ]*' /var/log/overleaf/web.log | tail -1` and open that link.
- **Something else**: `./texnest doctor` and `./texnest logs`. The design notes in [docs/DECISIONS.md](docs/DECISIONS.md) explain how the pieces fit together.
