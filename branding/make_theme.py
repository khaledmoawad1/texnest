#!/usr/bin/env python3
"""Generate branding/theme.css: Overleaf's brand-green tokens remapped to the TeXnest palette.

Usage: python3 branding/make_theme.py --primary '#2F3E4E' --accent '#D9A21B' [--dark-primary '#D9A21B'] [--out branding/theme.css]
Light surfaces use --primary; the dark chrome (Overleaf's "default" theme) uses --dark-primary with dark text.
"""
import argparse
import colorsys
from pathlib import Path

SUCCESS_LIGHT = {"--content-positive": "#2e7d32", "--content-positive-dark": "#6cc070",
                 "--notification-icon-success": "#2e7d32", "--notification-border-success": "#a5d6a7",
                 "--notification-bg-success": "#edf7ee", "--ds-color-text-success-default": "#1b5e20",
                 "--ds-color-text-success-hover": "#124116"}
SUCCESS_DARK = {"--content-positive": "#6cc070", "--content-positive-dark": "#6cc070",
                "--notification-icon-success": "#81c784", "--notification-border-success": "#2e7d32",
                "--notification-bg-success": "#1e3a22", "--ds-color-text-success-default": "#81c784",
                "--ds-color-text-success-hover": "#a5d6a7"}


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in rgb)


def shade(h, lightness, sat_scale=1.0):
    """Same hue as h at the given lightness (0-1); saturation scaled for tints."""
    r, g, b = (c / 255 for c in hex_to_rgb(h))
    hue, _, sat = colorsys.rgb_to_hls(r, g, b)
    return rgb_to_hex(tuple(c * 255 for c in colorsys.hls_to_rgb(hue, lightness, min(1, sat * sat_scale))))


def scales(primary):
    """Overleaf's legacy (10-70) and design-system (50-950) scales derived from one color."""
    r, g, b = (c / 255 for c in hex_to_rgb(primary))
    _, lig, _ = colorsys.rgb_to_hls(r, g, b)
    d = lambda delta: max(0.08, min(0.92, lig + delta))  # noqa: E731
    legacy = {10: shade(primary, 0.96, 0.6), 15: shade(primary, 0.92, 0.7), 20: shade(primary, 0.84, 0.8),
              30: shade(primary, 0.70), 40: shade(primary, 0.56), 50: primary,
              60: shade(primary, d(-0.08)), 65: shade(primary, d(-0.11)), 70: shade(primary, d(-0.15))}
    ds = {50: shade(primary, 0.97, 0.5), 100: shade(primary, 0.94, 0.6), 200: shade(primary, 0.86, 0.7),
          300: shade(primary, 0.74), 400: shade(primary, 0.60), 500: primary, 600: shade(primary, d(-0.06)),
          700: shade(primary, d(-0.10)), 800: shade(primary, d(-0.16)), 900: shade(primary, d(-0.24)),
          950: shade(primary, d(-0.32))}
    return legacy, ds


def tokens(primary, text_on_primary, dark):
    """Every token Overleaf derives from its green, redeclared with literal colors.
    Literal values are needed because custom properties declared on :root resolve there, not where they are used."""
    legacy, ds = scales(primary)
    p, p10, p20, p30, p60, p70 = primary, legacy[10], legacy[20], legacy[30], legacy[60], legacy[70]
    rgb = lambda h: ", ".join(str(c) for c in hex_to_rgb(h))  # noqa: E731
    tint, strong = (p70, p10) if dark else (p10, p70)       # soft background / text on it
    link, link_hover = (p30, p20) if dark else (p60, p70)   # readable link color for the surface
    t = {}
    t.update({f"--green-{k}": v for k, v in legacy.items()})
    t.update({f"--ds-color-green-{k}": v for k, v in ds.items()})
    t.update({"--bg-accent-01": p, "--bg-accent-02": p60, "--bg-accent-03": tint,
              "--btn-primary-background": p, "--btn-primary-hover-background": p60,
              "--btn-primary-hover-border": p60, "--btn-primary-color": text_on_primary,
              "--bs-primary": p, "--bs-primary-rgb": rgb(p),
              "--link-web": link, "--link-web-hover": link_hover, "--link-web-visited": link,
              "--link-web-dark": p30, "--link-web-hover-dark": p20, "--link-web-visited-dark": p30,
              "--bs-link-color": link, "--bs-link-color-rgb": rgb(link),
              "--bs-link-hover-color": link_hover, "--bs-link-hover-color-rgb": rgb(link_hover),
              "--dropdown-background-active": tint, "--dropdown-text-active": strong,
              "--checkbox-checked-bg": p, "--checkbox-checked-border-color": p,
              "--checkbox-hover-checked-bg": p60, "--checkbox-hover-checked-border-color": p60,
              "--toolbar-btn-active-bg-color": p, "--navbar-subdued-hover-color": p,
              "--theme-toggle-selected-background": p70 if dark else p20,
              "--outline-item-highlight-bg": tint, "--outline-item-highlight-color": strong,
              "--ide-rail-link-active-background": tint, "--ide-rail-link-active-color": strong,
              "--ide-settings-link-active-bg-color": tint, "--ide-settings-link-active-color": strong})
    t.update(SUCCESS_DARK if dark else SUCCESS_LIGHT)
    return "\n".join(f"  {k}: {v};" for k, v in t.items())


def components(primary, text_on_primary, prefix=""):
    """Components that hard-code Overleaf's green instead of using tokens."""
    legacy, _ = scales(primary)
    p, p60, p70 = primary, legacy[60], legacy[70]
    sel = lambda s: ", ".join(prefix + x.strip() for x in s.split(","))  # noqa: E731
    return "\n".join([
        f"{sel('.form-check-input:checked, .form-check-input[type=checkbox]:indeterminate')} {{ background-color: {p}; border-color: {p}; }}",
        f"{sel('.form-range::-webkit-slider-thumb')} {{ background-color: {p}; }}",
        f"{sel('.form-range::-moz-range-thumb')} {{ background-color: {p}; }}",
        f"{sel('.btn-outline-primary')} {{ --bs-btn-color: {p}; --bs-btn-border-color: {p}; --bs-btn-hover-color: {text_on_primary}; --bs-btn-hover-bg: {p};"
        f" --bs-btn-hover-border-color: {p}; --bs-btn-active-bg: {p60}; --bs-btn-active-border-color: {p60}; --bs-btn-disabled-color: {p}; --bs-btn-disabled-border-color: {p}; }}",
        f"{sel('.uppy-Dashboard-AddFiles-title button.uppy-Dashboard-browse')} {{ --bs-btn-color: {text_on_primary}; --bs-btn-bg: {p}; --bs-btn-border-color: {p};"
        f" --bs-btn-hover-bg: {p60}; --bs-btn-hover-border-color: {p60}; --bs-btn-active-bg: {p70}; --bs-btn-active-border-color: {p70}; --bs-btn-disabled-bg: {p}; --bs-btn-disabled-border-color: {p}; }}",
    ])


BRAND = """/* Brand assets. The lockup follows the navbar's real background (Overleaf's --navbar-bg rules),
   not its theme switch: the default navbar is dark, "website" navbars are light, and the dashboard's
   navbar is dark again under the default theme. Selectors match Overleaf's specificity. */
:root, [data-theme=default], [data-theme=light], [data-theme=dark] { --navbar-brand-width: 172px; }
.navbar-default .navbar-brand { gap: 0; }
.navbar-default .navbar-brand .navbar-logo { width: 172px; background-size: contain; background-position: left center; background-image: url(/img/texnest-lockup-dark.svg) !important; }
.website-redesign .navbar-default .navbar-brand .navbar-logo, .website-redesign-navbar .navbar-brand .navbar-logo { background-image: url(/img/texnest-lockup.svg) !important; }
[data-theme=default] #project-list-root .website-redesign .navbar-default .navbar-brand .navbar-logo, [data-theme=default] #library-root .website-redesign .navbar-default .navbar-brand .navbar-logo { background-image: url(/img/texnest-lockup-dark.svg) !important; }
.navbar-default .navbar-brand .navbar-title { display: none !important; }
/* Dashboard sidebar when the top navbar is hidden (Trash, Archived): Overleaf's vendor image becomes the lockup. */
.ds-nav-page-switcher-logo a { display: block; width: 150px; height: 36px; background: url(/img/texnest-lockup.svg) no-repeat left center / contain; }
[data-theme=default] .ds-nav-page-switcher-logo a, [data-theme=dark] .ds-nav-page-switcher-logo a { background-image: url(/img/texnest-lockup-dark.svg); }
.ds-nav-page-switcher-logo img { display: none; }
.ds-nav-ds-name { display: none; }
/* Editor home button */
:root, [data-theme=light] { --redesign-toolbar-logo-url: url(/img/texnest.svg); }
[data-theme=default], [data-theme=dark] { --redesign-toolbar-logo-url: url(/img/texnest-mark-dark.svg); }
.ide-redesign-toolbar .ide-redesign-toolbar-home-link .toolbar-ol-logo { background-image: var(--redesign-toolbar-logo-url); }
/* the accent is reserved for small highlights */
.beta-badge, .labs-badge, .labs-opt-in-wrapper .labs-icon { background-color: var(--texnest-accent); color: #1b222c; }
"""


def build(primary, accent, dark_primary, dark_text):
    dark_primary = dark_primary or primary
    modal = "[data-theme=default] .modal:not(.modal-themed), [data-theme=dark] .modal:not(.modal-themed)"
    return "\n".join([
        f"/* TeXnest theme, generated by branding/make_theme.py --primary {primary} --accent {accent} --dark-primary {dark_primary}. */",
        "/* Light surfaces: login and marketing pages, Overleaf's light theme. */",
        ":root, [data-theme=light] {", tokens(primary, "#ffffff", dark=False), f"  --texnest-accent: {accent};", "}",
        "/* Dark chrome (Overleaf's default theme): dashboard and editor. */",
        "[data-theme=default], [data-theme=dark] {", tokens(dark_primary, dark_text, dark=True), "}",
        "/* Dialogs stay light inside the dark chrome. */",
        modal + " {", tokens(primary, "#ffffff", dark=False), "}",
        components(primary, "#ffffff"),
        components(dark_primary, dark_text, "[data-theme=default] "),
        components(primary, "#ffffff", "[data-theme=default] .modal:not(.modal-themed) "),
        BRAND])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--primary", required=True, help="brand color for light surfaces, e.g. '#2F3E4E'")
    ap.add_argument("--accent", required=True, help="highlight color, e.g. '#D9A21B'")
    ap.add_argument("--dark-primary", default=None, help="primary for the dark chrome; a lighter tone that reads on dark")
    ap.add_argument("--dark-text", default="#1b222c", help="text color on the dark-chrome primary")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "theme.css"))
    a = ap.parse_args()
    for h in (a.primary, a.accent, a.dark_primary or a.primary, a.dark_text):
        if len(h.lstrip("#")) != 6:
            ap.error(f"{h} is not a 6-digit hex color")
    css = build(a.primary.lower(), a.accent.lower(), (a.dark_primary or "").lower() or None, a.dark_text.lower())
    Path(a.out).write_text(css)
    print(f"wrote {a.out} ({len(css.splitlines())} lines)")


if __name__ == "__main__":
    main()
