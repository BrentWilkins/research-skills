"""Linux browser smoke check in a disposable, already configured Hermes home. No model calls."""
import argparse
import functools
import http.server
import json
import os
from pathlib import Path
import re
import signal
import tempfile
import threading
import time
from unittest.mock import patch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--home', type=Path, required=True)
args = parser.parse_args()
home = args.home.resolve()
assert Path(tempfile.gettempdir()).resolve() in home.parents, 'Only disposable temp homes are accepted'
os.environ['HERMES_HOME'] = str(home)
os.environ.pop('BROWSER_CDP_URL', None)
from hermes_cli.plugins import discover_plugins
discover_plugins()
from model_tools import handle_function_call


def native(name, arguments, task='research-browser-smoke'):
    # Permit only this exact loopback fixture in the test process; no host policy is changed.
    with patch('tools.browser_tool._is_safe_url', side_effect=lambda target: target == url), patch('agent.auxiliary_client.call_llm') as model:
        result = json.loads(handle_function_call(name, arguments, task_id=task, user_task='Read fixture evidence'))
        model.assert_not_called()
    assert result.get('success'), result
    return result


def stop():
    profile = f'--user-data-dir={home / "research-browser"}'
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            arguments = path.read_bytes().decode().split('\0')
            if profile in arguments and not any(arg.startswith('--type=') for arg in arguments):
                os.kill(int(path.parent.name), signal.SIGTERM)
        except (OSError, UnicodeError):
            pass
    time.sleep(1)


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


with tempfile.TemporaryDirectory(prefix='research-browser-fixture-') as fixture:
    Path(fixture, 'index.html').write_text('''<!doctype html><title>Offline fixture</title><main></main>
<script>function render(){document.querySelector('main').innerHTML=document.cookie.includes('consent=yes')
? '<h1>Fixture evidence ready</h1><p>'+ 'Evidence passage. '.repeat(1500) +'</p>'
: '<button onclick="consent()">Reject optional cookies</button>';}
function consent(){document.cookie='consent=yes; Max-Age=86400; SameSite=Lax';render();}render();</script>''')
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=fixture))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    try:
        native('browser_navigate', {'url': url})
        snapshot = json.dumps(native('browser_snapshot', {'full': True}))
        match = re.search(r'button.*?Reject optional cookies.*?ref=(e\d+)', snapshot)
        assert match, snapshot
        native('browser_click', {'ref': match[1]})
        assert 'Fixture evidence ready' in json.dumps(native('browser_snapshot', {'full': True}))
        stop()
        native('browser_navigate', {'url': url}, task='research-browser-resumed')
        assert 'Fixture evidence ready' in json.dumps(native('browser_snapshot', {'full': True}, task='research-browser-resumed'))
        print('PASS: native browser navigation, consent, persisted cookies, restart, zero auxiliary model calls')
    finally:
        server.shutdown()
        server.server_close()
        stop()
