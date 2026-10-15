# Quick tools

Press **Super+U**, describe a task, then select a tool. Try `decode base64`,
`make json readable`, `remove url escapes`, `count words`, `compare text`,
`unix timestamp`, or `generate uuid`. Paste input in the tool window and use
its Copy button for the result. Escape cancels search without changing the clipboard.

One-time installation:

```sh
/usr/bin/python3 ~/thomas_config/scripts/quick-tools.py --install
```

Reload i3 configuration with **Super+Shift+C** after adding the binding.
The normal shortcut finder (**Super+F1**) also lists Quick tools.

All 86 tools come from the free, GPLv3 [official IT-Tools project](https://github.com/CorentinTh/it-tools).
The pinned [release v2024.10.22-7ca5933](https://github.com/CorentinTh/it-tools/releases/tag/v2024.10.22-7ca5933)
is the upstream project's latest packaged release as checked on 2026-10-14.
The installer checks its SHA-256 and archive paths before installing app files.
No conversions are reimplemented here.

The launcher starts one Python static server on `127.0.0.1:8787` when first needed.
Brave opens the selected tool in a floating app window with its own profile.
Common conversions work offline after installation. Input is pasted manually;
launch URLs contain only tool paths. Search matches words across tool descriptions,
keywords and handwritten aliases, then uses Rofi's fuzzy ranking. Matching words
keeps unrelated fuzzy subsequences out of results; unfamiliar wording may need
a shorter query.

Downloaded assets, Brave profile and server log live in the ignored `toolbox/.local/`
directory. Re-running `--install` repairs app files without replacing the profile.
To stop the server, find the process running `quick-tools.py --serve` and terminate it.
To remove the toolbox, stop that process, close its windows, then remove `toolbox/.local/`
and the Quick tools binding/window rule from i3. Browser profile data is stored locally
and follows the upstream app's storage behavior.

Checks:

```sh
./setup.sh check
i3 -C -c i3/config
```
