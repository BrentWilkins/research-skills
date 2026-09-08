"""No paid endpoints or model calls. Native Hermes web_extract provider."""
import datetime as dt
import email.utils
from filelock import FileLock
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from defusedxml import ElementTree as ET
from agent.web_search_provider import WebSearchProvider
from hermes_constants import get_hermes_home
from hermes_cli.config import read_raw_config
from tools.url_safety import is_safe_url
from tools.website_policy import check_website_access

EUTILS = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
BIOC = 'https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/'
CONVERTER = 'https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/'
MAX_BYTES = 12 * 1024 * 1024


class AccessError(Exception):
    pass


def check_url(url):
    if not is_safe_url(url):
        raise AccessError('Blocked: unsafe or private URL')
    blocked = check_website_access(url)
    if blocked:
        raise AccessError('Website policy: ' + blocked['message'])


def identify(url):
    p = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(p.path)
    host = (p.hostname or '').lower()
    if host == 'pubmed.ncbi.nlm.nih.gov' and re.fullmatch(r'/[0-9]+/?', path):
        return 'pmid', path.strip('/')
    if host in {'pmc.ncbi.nlm.nih.gov', 'www.ncbi.nlm.nih.gov'}:
        m = re.fullmatch(r'/(?:pmc/)?articles/(PMC[0-9]+)/?', path, re.I)
        if m:
            return 'pmcid', m[1].upper()
    if host in {'doi.org', 'dx.doi.org'} and re.fullmatch(r'/10\.[0-9]{4,9}/\S+', path):
        return 'doi', path[1:]
    return None


def xml_text(node):
    return ' '.join(''.join(node.itertext()).split()) if node is not None else ''


def pubmed_record(data, pmid):
    root = ET.fromstring(data)
    a = next((a for a in root.findall('./PubmedArticle')
              if xml_text(a.find('./MedlineCitation/PMID')) == pmid), None)
    if a is None:
        raise AccessError('PubMed returned no matching article')
    ids = {i.get('IdType'): xml_text(i) for i in a.findall('./PubmedData/ArticleIdList/ArticleId')}
    ids['pmid'] = pmid
    if ids.get('pmc'):
        ids['pmcid'] = ids['pmc']
    title = xml_text(a.find('./MedlineCitation/Article/ArticleTitle'))
    abstract = '\n\n'.join((x.get('Label', '') + ': ' if x.get('Label') else '') + xml_text(x)
                            for x in a.findall('./MedlineCitation/Article/Abstract/AbstractText'))
    journal = xml_text(a.find('./MedlineCitation/Article/Journal/Title'))
    return title, abstract, ids, journal


def bioc_record(data, pmcid):
    collections = json.loads(data)
    if not isinstance(collections, list):
        raise AccessError('BioC returned no article collection')
    docs = [d for c in collections for d in c.get('documents', [])]
    doc = next((d for d in docs if str(d.get('id', '')).removeprefix('PMC') == pmcid[3:]), None)
    if doc is None:
        raise AccessError('BioC returned no matching PMC article')
    passages = doc.get('passages', [])
    body_types = {'INTRO', 'METHODS', 'RESULTS', 'DISCUSS', 'CONCL', 'CASE', 'SUPPL', 'OTHER'}
    body = [p for p in passages if p.get('infons', {}).get('section_type') in body_types
            and p.get('text', '').strip()]
    if not body:
        raise AccessError('BioC has no article body; not full text')
    title = next((p.get('text', '') for p in passages
                  if p.get('infons', {}).get('section_type') == 'TITLE'), pmcid)
    parts, refs = [], []
    for p in passages:
        text = p.get('text', '').strip()
        if not text:
            continue
        section = p.get('infons', {}).get('section_type', 'OTHER')
        (refs if section == 'REF' else parts).append(f'## {section}\n{text}')
    if refs:
        parts.append('# References (cited works, not independently reviewed)\n' + '\n\n'.join(refs))
    return title, '\n\n'.join(parts)


def challenge_reason(content, status=None):
    try:
        code = int(status or 200)
    except (TypeError, ValueError):
        code = 200
    if code in {401, 402, 403, 429}:
        return {401: 'login_required', 402: 'subscription_required',
                403: 'access_denied', 429: 'rate_limited'}[code]
    if code >= 400:
        return 'http_error'
    # Short interstitials only: an article mentioning cookies is not blocked.
    text = re.sub(r'<[^>]+>', ' ', content).strip().lower()
    if len(text) < 3500:
        for phrase, reason in [
            ('cookies must be enabled', 'cookie_consent'),
            ('enable cookies for', 'cookie_consent'),
            ('verify you are human', 'bot_challenge'),
            ('checking your browser', 'bot_challenge'),
            ('enable javascript and cookies', 'javascript_challenge'),
            ('access denied', 'access_denied'),
            ('just a moment', 'bot_challenge'),
            ('subscribe to continue reading', 'subscription_required'),
        ]:
            if phrase in text:
                return reason
    return 'empty_content' if not text else None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # API endpoints are fixed. Never forward a local scrape request off-host.
        raise AccessError('Unexpected redirect; request was not followed')


class ResearchAccessProvider(WebSearchProvider):
    @property
    def name(self):
        return 'research-access'

    def is_available(self):
        return True

    def supports_extract(self):
        return True

    def _settings(self):
        return read_raw_config().get('research_access', {})

    def _cache_dir(self):
        path = get_hermes_home() / 'cache' / 'research-access'
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        return path

    def _pace(self):
        # Cross-process/profile pacing on this host, not just one tool call.
        import os
        import tempfile
        identity = str(os.getuid()) if hasattr(os, 'getuid') else hashlib.sha256(str(Path.home()).encode()).hexdigest()[:16]
        path = Path(tempfile.gettempdir()) / f'hermes-ncbi-{identity}.timestamp'
        with FileLock(str(path) + '.lock'):
            if path.is_symlink():
                raise AccessError('Unsafe NCBI pacing file')
            fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            with os.fdopen(fd, 'r+') as f:
                self._record_request_time(f)

    @staticmethod
    def _record_request_time(f):
        try:
            last = float(f.read() or 0)
        except ValueError:
            last = 0
        time.sleep(max(0, min(1.0, 1.0 - (time.time() - last))))
        f.seek(0)
        f.truncate()
        f.write(str(time.time()))
        f.flush()

    def _request(self, url, payload=None):
        is_local = payload is not None
        if not is_local:
            if not any(url.startswith(base) for base in (EUTILS, BIOC, CONVERTER)):
                raise AccessError('Unexpected API endpoint')
            check_url(url)
        # Local calls must ignore proxy env vars, including authenticated proxies.
        handlers = [NoRedirect()]
        if is_local:
            handlers.append(urllib.request.ProxyHandler({}))
        opener = urllib.request.build_opener(*handlers)
        for attempt in range(2):
            if not is_local:
                self._pace()
            req = urllib.request.Request(url, data=json.dumps(payload).encode() if is_local else None,
                                         headers={'User-Agent': 'HermesResearchAccess/1.0',
                                                  'Content-Type': 'application/json'})
            try:
                with opener.open(req, timeout=55 if is_local else 20) as r:
                    body = r.read(MAX_BYTES + 1)
                    if len(body) > MAX_BYTES:
                        raise AccessError('Response too large; not accepted as complete content')
                    return body
            except urllib.error.HTTPError as e:
                if e.code not in {429, 503} or attempt or is_local:
                    raise AccessError(f'HTTP {e.code}; access unavailable') from None
                delay = e.headers.get('Retry-After', '2')
                try:
                    seconds = float(delay)
                except ValueError:
                    try:
                        seconds = email.utils.parsedate_to_datetime(delay).timestamp() - time.time()
                    except (TypeError, ValueError):
                        seconds = 2
                if seconds > 10:
                    raise AccessError('Rate limited; retry later (Retry-After exceeds attempt budget)') from None
                time.sleep(max(0, seconds))

    def _api(self, base, **params):
        email = self._settings().get('ncbi_email')
        params['tool'] = 'hermes_research_access'
        if email:
            params['email'] = email
        return self._request(base + '?' + urllib.parse.urlencode(params))

    def _full_text(self, pmcid):
        if not re.fullmatch(r'PMC[0-9]+', pmcid):
            raise AccessError('Invalid PMC identifier')
        canonical = f'https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/'
        check_url(canonical)
        endpoint = BIOC + pmcid + '/unicode'
        title, body = bioc_record(self._request(endpoint), pmcid)
        return self._result(canonical, title, body, 'full_text', endpoint, {'pmcid': pmcid})

    def _result(self, canonical, title, body, coverage, endpoint, ids, warning=''):
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        header = (f'# {title}\n\nEvidence coverage: {coverage}\nCanonical source: {canonical}\n'
                  f'Retrieval: {endpoint}\nRetrieved at: {now}\n'
                  f'Identifiers: {json.dumps(ids, ensure_ascii=False)}\n'
                  'Coverage describes retrieved content, not study quality or proof that all sections were read.\n')
        if warning:
            header += f'Limitation: {warning}\n'
        if coverage == 'abstract_only':
            header += 'ABSTRACT ONLY: do not claim to have reviewed the full paper.\n'
        if endpoint.startswith((EUTILS, BIOC, CONVERTER)):
            header += 'NCBI disclaimer and copyright: https://www.ncbi.nlm.nih.gov/About/disclaimer.html\n'
        content = header + '\n' + body
        return {'url': canonical, 'title': title, 'content': content, 'raw_content': content,
                'metadata': {'coverage': coverage, 'canonical_url': canonical,
                             'retrieved_at': now, 'identifiers': ids, 'endpoint': endpoint}}

    def _scholarly(self, kind, identifier, expected_doi=None):
        if kind == 'pmcid':
            return self._full_text(identifier)
        if kind == 'doi':
            # E-utilities avoids the cookie-gated PMC web frontend entirely.
            search = ET.fromstring(self._api(EUTILS + 'esearch.fcgi', db='pubmed',
                                            term=f'"{identifier}"[AID]', retmode='xml', retmax=3))
            for candidate in search.findall('./IdList/Id'):
                pmid = xml_text(candidate)
                if re.fullmatch(r'[0-9]+', pmid):
                    try:
                        return self._scholarly('pmid', pmid, expected_doi=identifier)
                    except AccessError:
                        continue
            try:
                data = json.loads(self._api(CONVERTER, ids=identifier, idtype='doi', format='json'))
            except (ValueError, AccessError, OSError):
                return None
            rec = next((r for r in data.get('records', [])
                        if r.get('doi', '').lower() == identifier.lower() and r.get('pmcid')), None)
            if not rec:
                return None  # DOI outside PMC: try the publisher through local Firecrawl.
            result = self._full_text(rec['pmcid'])
            result['content'] = result['raw_content'] = result['content'] + f'\nRequested DOI: {identifier}\n'
            return result
        endpoint = EUTILS + 'efetch.fcgi'
        title, abstract, ids, journal = pubmed_record(
            self._api(endpoint, db='pubmed', id=identifier, retmode='xml'), identifier)
        if expected_doi and ids.get('doi', '').lower() != expected_doi.lower():
            raise AccessError('PubMed DOI does not match the requested DOI')
        warning = 'No PMC full-text identifier is present.'
        if ids.get('pmcid'):
            try:
                result = self._full_text(ids['pmcid'])
                # PubMed's own identifier list established this mapping.
                result['content'] = result['raw_content'] = result['content'] + f'\nPubMed PMID: {identifier}\nDOI: {ids.get("doi", "")}\n'
                return result
            except (AccessError, OSError, ValueError) as exc:
                warning = 'PMC full text unavailable through BioC: ' + type(exc).__name__
        if not abstract:
            raise AccessError('Matching PubMed metadata exists, but no abstract or full text was retrieved')
        return self._result(f'https://pubmed.ncbi.nlm.nih.gov/{identifier}/', title,
                            f'Journal: {journal}\n\n## Abstract\n{abstract}', 'abstract_only',
                            endpoint, ids, warning)

    def _local(self, url, format='markdown'):
        base = self._settings().get('firecrawl_url', 'http://127.0.0.1:13002').rstrip('/')
        p = urllib.parse.urlsplit(base)
        if p.scheme != 'http' or p.hostname not in {'127.0.0.1', '::1'} or p.username or p.password or p.path or p.query or p.fragment:
            raise AccessError('Only a literal loopback HTTP Firecrawl endpoint is permitted; hosted fallback is disabled')
        data = json.loads(self._request(base + '/v1/scrape',
                         {'url': url, 'formats': ['markdown'], 'timeout': 45000}))
        if not data.get('success'):
            raise AccessError('Local Firecrawl extraction failed')
        page = data.get('data') or {}
        meta = page.get('metadata') or {}
        final = meta.get('sourceURL') or url
        check_url(final)
        content = page.get('markdown') or ''
        reason = challenge_reason(content, meta.get('statusCode'))
        if reason:
            raise AccessError(f'{reason}: no usable evidence extracted. Try native browser_navigate/browser_snapshot; do not count this as a reviewed source.')
        return self._result(final, meta.get('title') or final, content, 'web_page',
                            'local Firecrawl', {}, 'Web extraction may omit content; verify the relevant sections.')

    def extract(self, urls, **kwargs):
        results = []
        from tools.interrupt import is_interrupted
        for url in urls:
            try:
                if is_interrupted():
                    raise AccessError('Interrupted')
                check_url(url)
                identity = identify(url)
                key = hashlib.sha256(repr(identity).encode()).hexdigest()
                path = self._cache_dir() / (key + '.json')
                result = None
                if identity:
                    # Check resolved destination policy even on cache hits.
                    try:
                        cached = json.loads(path.read_text())
                        if time.time() - path.stat().st_mtime < 86400:
                            check_url(cached['metadata']['canonical_url'])
                            result = cached
                    except (OSError, ValueError, KeyError):
                        pass
                    if result is None:
                        result = self._scholarly(*identity)
                        if result:
                            import os
                            import tempfile
                            fd, tmp = tempfile.mkstemp(dir=path.parent)
                            try:
                                with os.fdopen(fd, 'w') as f:
                                    json.dump(result, f)
                                os.replace(tmp, path)
                            finally:
                                if os.path.exists(tmp):
                                    os.unlink(tmp)
                if result is None:
                    result = self._local(url, kwargs.get('format', 'markdown'))
                result['url'] = url
                results.append(result)
            except Exception as exc:
                # Avoid leaking query strings, credentials or response bodies via errors.
                message = str(exc) if isinstance(exc, AccessError) else f'Retrieval failed ({type(exc).__name__})'
                results.append({'url': url, 'title': '', 'content': '', 'error': message})
        return results


class LocalFirecrawlCompatibilityProvider(ResearchAccessProvider):
    """Startup-only replacement: existing processes retain their loaded provider."""
    @property
    def name(self):
        return 'firecrawl'

    @property
    def display_name(self):
        return 'Local research access (Firecrawl compatibility)'
