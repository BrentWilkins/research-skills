#!/usr/bin/env python3
"""Start only the dedicated local research browser; print its CDP URL."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request


def ensure_browser(home, port=9223, binary=None):
    if not 1024 <= port <= 65535:
        raise RuntimeError('Browser port must be between 1024 and 65535')
    endpoint = f'http://127.0.0.1:{port}'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def ready():
        try:
            with opener.open(endpoint + '/json/version', timeout=1) as r:
                return bool(json.load(r).get('webSocketDebuggerUrl'))
        except (OSError, ValueError):
            return False

    if ready():
        return endpoint
    binary = binary or next((shutil.which(x) for x in ('google-chrome', 'chromium', 'chromium-browser')
                   if shutil.which(x)), None)
    if not binary:
        raise RuntimeError('Install a local Chrome/Chromium browser before using the research fallback')
    profile = home / 'research-browser'
    profile.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (profile / 'startup.log').open('ab') as log:
        proc = subprocess.Popen([
            binary, '--headless=new', '--disable-gpu', '--no-first-run',
            '--no-default-browser-check', '--disable-background-networking',
            '--remote-debugging-address=127.0.0.1', f'--remote-debugging-port={port}',
            f'--user-data-dir={profile}', 'about:blank',
        ], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    for _ in range(50):
        if ready():
            return endpoint
        if proc.poll() is not None:
            break
        time.sleep(.2)
    raise RuntimeError(f'Research browser did not become ready; see {profile / "startup.log"}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--home', type=Path, default=Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes')))
    parser.add_argument('--port', type=int, default=9223)
    args = parser.parse_args()
    print(ensure_browser(args.home, args.port))
