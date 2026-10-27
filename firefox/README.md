# Firefox: Cozy Mint Gradient

The desktop palette with a quiet dark sage-to-lavender gradient, mint accents,
cream text and ComicShannsMono in Firefox's interface and new-tab page.

The CSS and manifest are generated from the selected desktop TOML preset. Run
setup before linking or loading them. Use `theme apply` to generate another
palette, then restart Firefox when convenient. Change shared selectors under
`themes/templates/firefox/`; generated files are overwritten on application.

## Local setup

`userChrome.css` styles the browser interface. `userContent.css` styles only
`about:home` and `about:newtab`.

1. Open `about:profiles` and find the profile marked as currently in use.
2. Open its **Root Directory** and create a `chrome` folder.
3. Link or copy these two CSS files into that folder, keeping their names.
4. In `about:config`, set
   `toolkit.legacyUserProfileCustomizations.stylesheets` to `true`.
5. Restart Firefox once to load the style.

Alternatively, run `./setup.sh apply --configs-only` from the repository root.
Setup detects the default native or Ubuntu Snap profile and links these CSS
files and `user.js`. Run Firefox once first if no profile exists yet. Regular
Firefox windows and the browser scratchpad share the default profile.

## Scratchpad behavior

`Super+G` shows or hides Firefox without pausing it. Clipboard transfers, audio,
downloads, and page activity continue while hidden. The existing shortcut picks
up script changes immediately; no desktop or browser restart is required.

Restarting reloads saved tabs, but active page activity can reset. Apply the
style during a convenient restart.

To remove the style, remove the two links from the profile's `chrome` folder
and restart Firefox. Firefox updates can change interface selectors; this
version was checked with Firefox 157.

## Firefox theme package

`manifest.json` is a Firefox-native, data-only theme with the same colors and
header gradient. Firefox 156+ is required for its gradient sizing properties.
It declares no extension scripts, permissions or external resources.

For a temporary preview, open `about:debugging#/runtime/this-firefox`, choose
**Load Temporary Add-on**, then select this `manifest.json`. Temporary themes
are removed when Firefox exits. A permanent package install in release
Firefox requires Mozilla signing; the local CSS setup above persists without
an extension.

Brave's manifest needs conversion: Firefox uses keys such as `toolbar_field`,
`icons` and `tab_selected`, rather than Chromium's `omnibox_*`,
`toolbar_button_icon` and `background_tab`. Copying the Brave folder directly
does not provide a complete Firefox theme.

References: [Mozilla theme format](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/theme)
and [Mozilla signing requirements](https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/).
