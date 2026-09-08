"""Optional native Hermes smoke test; use a disposable home configured by setup.py."""
import argparse
import asyncio
import json
import os
from pathlib import Path
from unittest.mock import patch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--home', type=Path, required=True)
parser.add_argument('--live', action='store_true', help='Retrieve one public PubMed abstract through native web_extract')
args = parser.parse_args()
os.environ['HERMES_HOME'] = str(args.home)
os.environ.pop('BROWSER_CDP_URL', None)

from hermes_cli.plugins import discover_plugins
discover_plugins()
from tools.web_tools import _registered_web_provider, web_extract_tool

provider = _registered_web_provider('research-access')
assert provider and provider.is_available(), 'Plugin was not registered'


async def checks():
    if args.live:
        result = json.loads(await web_extract_tool(['https://pubmed.ncbi.nlm.nih.gov/17284678/'], char_limit=4000))
        source = result['results'][0]
        assert not source.get('error'), source.get('error')
        assert 'Evidence coverage:' in source['content']
        print('PASS: native web_extract, scholarly identity and coverage')
    else:
        with patch.object(provider, '_local', return_value={'url': 'https://example.com', 'title': 'Fixture', 'content': 'Offline evidence'}):
            result = json.loads(await web_extract_tool(['https://example.com'], char_limit=4000))
        assert not result['results'][0].get('error'), result
        print('PASS: native plugin discovery and web_extract dispatch')
    from hermes_cli.config import read_raw_config
    if read_raw_config().get('research_access', {}).get('browser_enabled'):
        from model_tools import handle_function_call
        with patch('agent.auxiliary_client.call_llm') as llm:
            denied = handle_function_call('browser_vision', {'question': 'fixture'}, task_id='research-plugin-smoke')
            assert 'disabled' in denied, denied
            llm.assert_not_called()
        print('PASS: browser vision auxiliary-model guard')


asyncio.run(checks())
