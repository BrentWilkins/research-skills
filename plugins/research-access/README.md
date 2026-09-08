# Setup and maintenance

Install this plugin with `hermes plugins install BrentWilkins/research-skills/plugins/research-access`.
Then run `python3 ~/.hermes/plugins/research-access/setup.py` (adjust for a custom Hermes home).
The setup installs the dependencies from the included lockfiles and enables the extraction backend.
It does not run merely because a skill is downloaded or read.

Prerequisites: a working Hermes installation, uv, and (for browser setup) Node.js/npm.
Linux is tested. macOS has not been validated; native Windows is refused (use WSL).

```sh
python3 ~/.hermes/plugins/research-access/setup.py
```

The installer finds Hermes's Python and uses it to create a separate dependency environment
under `HERMES_HOME/plugins/research-access/.venv`. `uv sync --locked` installs defusedxml,
PyYAML, and filelock. Hermes's own environment and lockfile are not modified. Hermes loads
the plugin in-process; already loaded host modules are not replaced with different versions.

Browser setup uses `npm ci` in the installed plugin, never a global npm installation or a
workspace-dependent symlink. It reuses system Chrome/Chromium if present; otherwise the
browser helper downloads Chrome into a dedicated cache. OS browser libraries may still be
required on minimal Linux systems; the installer does not run privileged OS package commands.
The agent-browser compatibility range follows Hermes's verified `agent-browser@^0.26.0`
requirement. Dependency changes must use uv/npm and update their committed lockfiles.

Configuration changes: select `web.extract_backend: research-access`, enable that plugin,
and, unless `--no-browser` is used, select a dedicated loopback CDP browser and grant this
plugin's browser snapshot override. Search, model settings, and existing skills are preserved.
The plugin does not replace the built-in `firecrawl` provider registration by default.

`--no-browser` omits npm/browser setup and all browser-tool hooks. `--browser-port` selects a
dedicated CDP port (default 9223). `--firecrawl-url` configures an existing literal loopback HTTP
Firecrawl service (default `http://127.0.0.1:13002`). The installer does not deploy Firecrawl,
SearXNG, Docker, or a search provider. NCBI scholarly extraction works without Firecrawl;
ordinary pages can use the configured local service or agent-directed native browser fallback.
Search uses the working provider already configured in Hermes.

All files needed for setup live within this plugin directory; Hermes's plugin installer retrieves them.
No tokens, browser profiles, caches, downloaded dependencies, or user configuration are bundled.

## Updating and rollback

Exit active Hermes sessions before replacing the plugin. `--replace` moves the previous
plugin into a timestamped directory under `HERMES_HOME/backups/` and saves config.yaml there.
Dependency/setup failure restores the previous plugin and leaves configuration unchanged.
The installer prints the exact backup path; it never prints configuration contents.

For rollback, stop Hermes, move the new `plugins/research-access` directory aside, restore
the saved plugin directory (if there was one), and restore the backed-up config after
accounting for any later edits. If no plugin existed before installation, restore config and
leave the new plugin disabled. Restart Hermes. Do not remove an ordinary personal browser profile.

Compression of research reports is independent of this setup: the research skill uses only
standard-library codecs and falls back to uncompressed ZIP if necessary.
