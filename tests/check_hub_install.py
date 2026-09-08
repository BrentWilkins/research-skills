"""Verify authenticated Skills Hub delivery into a disposable Hermes home."""
import argparse
import os
from pathlib import Path
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--home', type=Path, required=True)
parser.add_argument('--repo', required=True)
parser.add_argument('--plugin-source', help='Also exercise native plugin installation from this Git identifier')
args = parser.parse_args()
assert Path(tempfile.gettempdir()).resolve() in args.home.resolve().parents
os.environ['HERMES_HOME'] = str(args.home)

from hermes_cli.skills_hub import do_install, do_tap
from tools.skills_hub import TapsManager
from tools.skills_hub_github import GitHubAuth, GitHubSource

do_tap('add', args.repo)
source = GitHubSource(GitHubAuth(), extra_taps=TapsManager().list_taps())
source.taps = [tap for tap in source.taps if tap['repo'] == args.repo]
found = {item.identifier for item in source.search('research')}
for name in ('deep-researcher', 'hermes-research-access'):
    identifier = f'{args.repo}/skills/{name}'
    assert identifier in found, f'Tap failed to discover {name}'
    do_install(identifier, category='research', skip_confirm=True, invalidate_cache=False)
    directory = args.home / 'skills/research' / name
    assert (directory / 'SKILL.md').is_file(), f'Skill installation failed: {name}'
access = args.home / 'skills/research/hermes-research-access'
for name in ('references/setup.md',):
    assert (access / name).is_file(), f'Support file missing: {name}'
print('PASS: tap discovery and both Skills Hub installs include runtime setup instructions')
if args.plugin_source:
    from hermes_cli.plugins_cmd import cmd_install
    cmd_install(args.plugin_source, enable=False)
    plugin = args.home / 'plugins/research-access'
    for name in ('setup.py', 'provider.py', 'uv.lock', 'browser-runtime/package-lock.json'):
        assert (plugin / name).is_file(), f'Plugin file missing: {name}'
    print('PASS: native plugin installation with code and dependency locks; setup still required')
