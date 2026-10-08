# Brave: Cozy Mint

A color-only theme matching [theme.sh](../theme.sh) and the
[Kitty palette](../kitty/current-theme.conf).

## Install

1. Open `brave://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select this folder: `/home/thomas/thomas_config/brave`.

For dark browser dialogs and settings pages, also set Brave's color mode
to **Dark** in browser settings.

## Palette

| Color | Hex | Use |
| --- | --- | --- |
| Near-black | `#191B19` | Window frame, inactive tabs, address bar |
| Dark sage | `#272C27` | Toolbar and active tab surface |
| Cream | `#EEE8DC` | Address bar, toolbar and bookmark text |
| Mint | `#A7CCAE` | Active tab text and toolbar icons |
| Muted sage | `#ABAFA4` | Inactive tab text |
| Lavender | `#C0AFD5` | Chromium new-tab header |

## New tab page

Brave manages its new-tab background separately. Open a new tab, click
**Customize**, then choose a solid background or upload
[`wallpapers/hoppers.png`](../wallpapers/hoppers.png) to match the desktop.
The `ntp_*` colors also support Chromium's standard new-tab page.

## Edit or remove

Edit `theme.colors` in `manifest.json`; colors are RGB arrays, such as
`[167, 204, 174]` for mint. Load this folder again to apply changes.

To remove the theme on Linux, open `brave://settings/appearance` and click
**Use Classic**.

References: [Chromium theme format](https://developer.chrome.com/docs/extensions/mv2/themes)
and [Brave new-tab customization](https://support.brave.com/hc/en-us/articles/360040912932-How-do-I-customize-my-New-Tab-Page).
