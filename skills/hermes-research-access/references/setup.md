# Install the runtime

When asked to set up research access, use Hermes's native plugin installer:

```sh
hermes plugins install BrentWilkins/research-skills/plugins/research-access
python3 ~/.hermes/plugins/research-access/setup.py
```

Adjust the setup path and pass `--home` for a nondefault Hermes home. The installer applies
Hermes's plugin-specific security scan. Do not bypass a blocked scan; report its findings.
Setup needs uv and, for browser support, Node.js/npm. It installs locked Python dependencies
in the plugin's separate environment and the locked browser helper locally. It preserves
search/model settings and existing skills, backs up configuration, and selects the new
extraction backend. Start a new Hermes session afterward.

Use `--no-browser` to omit browser setup, `--hermes-python` if runtime detection fails,
and `--replace` for a backed-up reinstall from a separate source checkout. Running setup
inside a natively installed plugin configures that installation in place.

The runtime supports scholarly APIs independently. Ordinary-page extraction needs an existing
local Firecrawl service or the native browser fallback. A working Hermes search provider is
still required. Setup does not deploy search services, Docker, or privileged OS packages.

See the [plugin documentation](https://github.com/BrentWilkins/research-skills/tree/main/plugins/research-access)
for configuration effects, supported platforms, browser prerequisites, and rollback.
