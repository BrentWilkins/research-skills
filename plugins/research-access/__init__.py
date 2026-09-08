import os
from pathlib import Path
import sys

_root = Path(__file__).resolve().parent
_site = (_root / '.venv/Lib/site-packages' if os.name == 'nt' else
         _root / f'.venv/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages')
if not _site.is_dir():
    raise RuntimeError('Research-access dependencies missing; rerun setup with Hermes Python.')
sys.path.append(str(_site))

from .provider import ResearchAccessProvider, LocalFirecrawlCompatibilityProvider


def ensure_local_browser(tool_name, **kwargs):
    from hermes_cli.config import read_raw_config
    if not read_raw_config().get('research_access', {}).get('browser_enabled', False):
        return None
    if tool_name == 'browser_vision':
        return {'action': 'block', 'message': 'Research access is local-only: use browser_snapshot for text; screenshot model analysis is disabled to avoid auxiliary-model charges.'}
    if not tool_name.startswith('browser_'):
        return None
    import os
    from hermes_cli.config import read_raw_config
    from hermes_constants import get_hermes_home
    from .ensure_browser import ensure_browser
    config = read_raw_config()
    port = int(config.get('research_access', {}).get('browser_port', 9223))
    expected = f'http://127.0.0.1:{port}'
    configured = os.environ.get('BROWSER_CDP_URL') or config.get('browser', {}).get('cdp_url')
    if configured != expected:
        return {'action': 'block', 'message': 'Research-access browser configuration differs from its dedicated local endpoint; review the selected browser before continuing.'}
    try:
        ensure_browser(get_hermes_home(), port, config.get('research_access', {}).get('browser_binary'))
    except (OSError, RuntimeError) as exc:
        return {'action': 'block', 'message': f'Local research browser unavailable: {exc}'}
    return None


def register(ctx):
    ctx.register_web_search_provider(ResearchAccessProvider())
    # Hermes explicitly supports provider replacements and restores them on
    # plugin unload. Bundled backends load before opt-in user plugins.
    # Retaining the configured name avoids breaking an already-running Hermes
    # process which cannot discover a new backend without a plugin reload.
    from hermes_cli.config import read_raw_config
    if read_raw_config().get('research_access', {}).get('replace_local_firecrawl', False):
        ctx.register_web_search_provider(LocalFirecrawlCompatibilityProvider())
    if not read_raw_config().get('research_access', {}).get('browser_enabled', False):
        return
    os.environ['PATH'] = str(_root / 'browser-runtime/node_modules/.bin') + os.pathsep + os.environ.get('PATH', '')
    ctx.register_hook('pre_tool_call', ensure_local_browser)
    # Preserve the native schema and cache/truncation behavior, but never pass
    # user_task to the optional auxiliary-LLM snapshot summarizer.
    from tools import browser_tool
    try:
        from tools.browser_tool_install import check_browser_requirements
    except ImportError:
        check_browser_requirements = browser_tool.check_browser_requirements
    from tools.registry import registry

    def local_snapshot(args, **kwargs):
        return browser_tool.browser_snapshot(full=args.get('full', False),
                                             task_id=kwargs.get('task_id'), user_task=None)

    ctx.register_tool(name='browser_snapshot', toolset='browser',
                      schema=registry.get_schema('browser_snapshot'),
                      handler=local_snapshot, check_fn=check_browser_requirements,
                      override=True, emoji='🖼️')
