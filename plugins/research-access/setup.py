#!/usr/bin/env python3
"""Install research-access and locked dependencies without modifying Hermes's environment."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

BUNDLE = Path(__file__).resolve().parent
FILES = ('setup.py', '__init__.py', 'provider.py', 'ensure_browser.py', 'plugin.yaml', 'pyproject.toml',
         'uv.lock', 'browser-runtime/package.json', 'browser-runtime/package-lock.json')


def execute(command, **kwargs):
    subprocess.run(command, check=True, **kwargs)


def find_python(home, supplied):
    candidates = [supplied] if supplied else []
    launcher = shutil.which('hermes')
    if launcher:
        try:
            first = Path(launcher).read_text().splitlines()[0]
            if first.startswith('#!') and Path(first[2:]).is_file():
                candidates.append(first[2:])
        except (OSError, UnicodeError):
            pass
    candidates += [home / 'hermes-agent/venv/bin/python', home / 'hermes-agent/.venv/bin/python', sys.executable]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            result = subprocess.run([str(candidate), '-c', 'import hermes_constants, yaml; from agent.web_search_provider import WebSearchProvider'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode == 0:
                return str(candidate)
    raise RuntimeError('Pass --hermes-python /path/to/hermes/python; Hermes Python was not found.')


def atomic(path, text):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(args):
    if os.name == 'nt':
        raise RuntimeError('Use Hermes in WSL; native Windows setup is not yet supported.')
    home = args.home.expanduser().absolute()
    plugin, config_path = home / 'plugins/research-access', home / 'config.yaml'
    if any(path.is_symlink() for path in (home, plugin.parent, plugin, config_path)):
        raise RuntimeError('Refusing a symlinked home, plugin directory, or configuration.')
    in_place = plugin.resolve() == BUNDLE.resolve()
    if plugin.exists() and not in_place and not args.replace:
        raise RuntimeError('Plugin exists; use --replace for a backed-up reinstall.')
    uv, npm = shutil.which('uv'), shutil.which('npm')
    if not uv:
        raise RuntimeError('Install uv, then rerun setup. Hermes normally already uses uv.')
    if not args.no_browser and not npm:
        raise RuntimeError('Install Node.js/npm or select --no-browser for scholarly retrieval only.')
    python = find_python(home, args.hermes_python)
    original = config_path.read_text(encoding='utf-8') if config_path.exists() else None
    parsed = subprocess.run([python, '-c', 'import json,sys,yaml; print(json.dumps(yaml.safe_load(sys.stdin.read()) or {}))'],
                            input=original or '', text=True, capture_output=True, check=True)
    config = json.loads(parsed.stdout)
    if not isinstance(config, dict):
        raise RuntimeError('Hermes configuration must be a mapping.')
    if not 1024 <= args.browser_port <= 65535:
        raise RuntimeError('Browser port must be between 1024 and 65535.')
    endpoint = f'http://127.0.0.1:{args.browser_port}'
    existing = config.get('browser', {}).get('cdp_url')
    if not args.no_browser and existing and existing != endpoint:
        raise RuntimeError('A different browser is configured. Select --no-browser or reconfigure it explicitly.')
    if args.firecrawl_url:
        url = urlsplit(args.firecrawl_url)
        if url.scheme != 'http' or url.hostname not in {'127.0.0.1', '::1'} or url.username or url.password or url.path or url.query or url.fragment:
            raise RuntimeError('--firecrawl-url must be a literal loopback HTTP origin.')
    home.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = home / 'backups' / ('research-access-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    if original is not None:
        atomic(backup / 'config.yaml', original)
    plugin.parent.mkdir(parents=True, exist_ok=True)
    if plugin.exists() and not in_place:
        plugin.rename(backup / 'plugin')
    plugin.mkdir(exist_ok=in_place)
    try:
        for name in FILES:
            source, target = BUNDLE / name, plugin / name
            if not source.is_file() or source.is_symlink():
                raise RuntimeError(f'Missing or unsafe bundle file: {name}')
            target.parent.mkdir(parents=True, exist_ok=True)
            if not in_place:
                shutil.copy2(source, target)
        execute([uv, 'sync', '--project', str(plugin), '--locked', '--no-dev', '--python', python])
        binary = None
        if not args.no_browser:
            runtime = plugin / 'browser-runtime'
            execute([npm, 'ci', '--no-audit', '--no-fund'], cwd=runtime)
            binary = next((shutil.which(name) for name in ('google-chrome', 'chromium', 'chromium-browser') if shutil.which(name)), None)
            if not binary:
                cache = home / 'cache/research-browser-download'
                execute([str(runtime / 'node_modules/.bin/agent-browser'), 'install'],
                        env=dict(os.environ, XDG_CACHE_HOME=str(cache)))
                binaries = [path for path in cache.rglob('*') if path.name in ('chrome', 'Chromium', 'Google Chrome for Testing') and path.is_file() and os.access(path, os.X_OK)]
                if not binaries:
                    raise RuntimeError('Install Chrome/Chromium and rerun; the downloaded browser was not found.')
                binary = str(binaries[0])
        config.setdefault('web', {})['extract_backend'] = 'research-access'
        enabled = config.setdefault('plugins', {}).setdefault('enabled', [])
        if 'research-access' not in enabled:
            enabled.append('research-access')
        disabled = config['plugins'].get('disabled', [])
        if 'research-access' in disabled:
            disabled.remove('research-access')
        settings = config.setdefault('research_access', {})
        settings.update(replace_local_firecrawl=False, browser_enabled=not args.no_browser, browser_port=args.browser_port)
        if args.firecrawl_url:
            settings['firecrawl_url'] = args.firecrawl_url
        settings.setdefault('firecrawl_url', 'http://127.0.0.1:13002')
        if not args.no_browser:
            settings['browser_binary'] = binary
            config.setdefault('browser', {})['cdp_url'] = endpoint
            config['plugins'].setdefault('entries', {}).setdefault('research-access', {})['allow_tool_override'] = True
        rendered = subprocess.run([python, '-c', 'import json,sys,yaml; print(yaml.safe_dump(json.load(sys.stdin),sort_keys=False),end="")'],
                                  input=json.dumps(config), text=True, capture_output=True, check=True).stdout
        atomic(config_path, rendered)
    except BaseException:
        if not in_place:
            shutil.rmtree(plugin)  # exact new installation only; never a workspace/home
            if (backup / 'plugin').exists():
                (backup / 'plugin').rename(plugin)
        raise
    print(f'Installed research-access. Backup: {backup}')
    print('Start a new Hermes session. Existing skills, search, and model settings were preserved.')
    print('Scholarly APIs are ready. Ordinary-page extraction needs a running local Firecrawl endpoint.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path(os.environ.get('HERMES_HOME', str(Path.home() / '.hermes'))))
    parser.add_argument('--hermes-python')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--browser-port', type=int, default=9223)
    parser.add_argument('--firecrawl-url')
    parser.add_argument('--replace', action='store_true')
    try:
        install(parser.parse_args())
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Setup failed: {type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    main()
