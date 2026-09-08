"""Installer preservation/rollback checks with dependency downloads stubbed out."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'plugins/research-access/setup.py'
spec = importlib.util.spec_from_file_location('research_setup', SCRIPT)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = {'model': {'default': 'fixture-model'}, 'web': {'search_backend': 'fixture-search'},
                       'plugins': {'enabled': ['existing'], 'disabled': ['research-access', 'unrelated']}}
        (self.home / 'config.yaml').write_text(json.dumps(self.config))
        self.args = SimpleNamespace(home=self.home, replace=False, no_browser=True,
                                    hermes_python=sys.executable, browser_port=19323, firecrawl_url=None)
        for target, value in (
            ('find_python', lambda *args: sys.executable),
            ('execute', lambda *args, **kwargs: None),
        ):
            mocker = patch.object(setup, target, value)
            mocker.start()
            self.addCleanup(mocker.stop)
        mocker = patch.object(setup.shutil, 'which', return_value='/fixture/uv')
        mocker.start()
        self.addCleanup(mocker.stop)
        # Fixture configuration is JSON (valid YAML); simulate Hermes's YAML conversion only.
        mocker = patch.object(setup.subprocess, 'run', side_effect=lambda *args, **kwargs: SimpleNamespace(stdout=kwargs['input']))
        mocker.start()
        self.addCleanup(mocker.stop)

    def test_preserves_unrelated_config_and_skills(self):
        skill = self.home / 'skills/research/deep-researcher/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('Existing customized instructions')
        setup.install(self.args)
        result = json.loads((self.home / 'config.yaml').read_text())
        self.assertEqual(result['model'], self.config['model'])
        self.assertEqual(result['web']['search_backend'], 'fixture-search')
        self.assertEqual(result['web']['extract_backend'], 'research-access')
        self.assertEqual(result['plugins']['enabled'], ['existing', 'research-access'])
        self.assertEqual(result['plugins']['disabled'], ['unrelated'])
        self.assertFalse(result['research_access']['browser_enabled'])
        self.assertEqual(skill.read_text(), 'Existing customized instructions')
        self.assertEqual(len(list((self.home / 'backups').glob('*/config.yaml'))), 1)

    def test_existing_plugin_requires_replace(self):
        plugin = self.home / 'plugins/research-access'
        plugin.mkdir(parents=True)
        (plugin / 'custom.txt').write_text('keep')
        with self.assertRaisesRegex(RuntimeError, 'exists'):
            setup.install(self.args)
        self.assertEqual((plugin / 'custom.txt').read_text(), 'keep')

    def test_dependency_failure_restores_previous_install(self):
        plugin = self.home / 'plugins/research-access'
        plugin.mkdir(parents=True)
        (plugin / 'custom.txt').write_text('keep')
        original = (self.home / 'config.yaml').read_bytes()
        self.args.replace = True
        with patch.object(setup, 'execute', side_effect=subprocess.CalledProcessError(1, ['uv', 'sync'])):
            with self.assertRaises(subprocess.CalledProcessError):
                setup.install(self.args)
        self.assertEqual((plugin / 'custom.txt').read_text(), 'keep')
        self.assertEqual((self.home / 'config.yaml').read_bytes(), original)

    def test_remote_endpoint_and_symlinks_refused(self):
        self.args.firecrawl_url = 'https://api.firecrawl.dev'
        with self.assertRaisesRegex(RuntimeError, 'loopback'):
            setup.install(self.args)
        self.args.firecrawl_url = None
        plugin = self.home / 'plugins/research-access'
        plugin.parent.mkdir()
        plugin.symlink_to(self.home)
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            setup.install(self.args)


if __name__ == '__main__':
    unittest.main()
