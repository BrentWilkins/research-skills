"""Behavioral tests; run with Hermes's interpreter (stdlib unittest)."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('research_provider', Path(__file__).with_name('provider.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

PUBMED = b'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID>
<Article><ArticleTitle>Study <i>title</i></ArticleTitle><Journal><Title>Journal</Title></Journal>
<Abstract><AbstractText Label="METHODS">Human trial.</AbstractText></Abstract></Article>
</MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="pubmed">123</ArticleId>
<ArticleId IdType="pmc">PMC456</ArticleId><ArticleId IdType="doi">10.1234/test</ArticleId>
</ArticleIdList><ReferenceList><Reference><ArticleIdList><ArticleId IdType="pmc">PMC999</ArticleId>
</ArticleIdList></Reference></ReferenceList></PubmedData></PubmedArticle></PubmedArticleSet>'''


def bioc(identifier='456', body=True):
    passages = [{'infons': {'section_type': 'TITLE'}, 'text': 'Full paper'},
                {'infons': {'section_type': 'ABSTRACT'}, 'text': 'Summary'}]
    if body:
        passages += [{'infons': {'section_type': 'METHODS'}, 'text': 'Trial methods.'},
                     {'infons': {'section_type': 'REF'}, 'text': 'Cited work'}]
    return json.dumps([{'documents': [{'id': identifier, 'passages': passages}]}]).encode()


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for target, value in [('check_url', lambda url: None),
                              ('get_hermes_home', lambda: Path(self.temp.name)),
                              ('read_raw_config', lambda: {})]:
            patcher = patch.object(p, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.provider = p.ResearchAccessProvider()

    def test_identification_requires_exact_host_and_article_path(self):
        self.assertEqual(p.identify('https://pubmed.ncbi.nlm.nih.gov/123/'), ('pmid', '123'))
        self.assertEqual(p.identify('https://www.ncbi.nlm.nih.gov/pmc/articles/PMC456/'), ('pmcid', 'PMC456'))
        self.assertEqual(p.identify('https://doi.org/10.1234/test'), ('doi', '10.1234/test'))
        self.assertIsNone(p.identify('https://pubmed.ncbi.nlm.nih.gov.evil.test/123/'))
        self.assertIsNone(p.identify('https://pubmed.ncbi.nlm.nih.gov/?term=test'))

    def test_citation_identity_excludes_reference_ids(self):
        title, abstract, ids, journal = p.pubmed_record(PUBMED, '123')
        self.assertEqual(ids['pmcid'], 'PMC456')
        self.assertIn('METHODS: Human trial.', abstract)
        self.assertEqual(title, 'Study title')
        with self.assertRaises(p.AccessError):
            p.pubmed_record(PUBMED, '999')

    def test_bioc_requires_matching_identity_and_actual_body(self):
        with self.assertRaises(p.AccessError):
            p.bioc_record(bioc('999'), 'PMC456')
        with self.assertRaises(p.AccessError):
            p.bioc_record(bioc(body=False), 'PMC456')
        _, content = p.bioc_record(bioc(), 'PMC456')
        self.assertIn('## METHODS', content)
        self.assertIn('References (cited works, not independently reviewed)', content)

    def test_pubmed_follows_own_pmc_id_and_caches(self):
        def request(url, payload=None):
            if 'efetch' in url:
                return PUBMED
            self.assertIn('PMC456', url)
            return bioc()
        with patch.object(self.provider, '_request', side_effect=request) as req:
            result = self.provider.extract(['https://pubmed.ncbi.nlm.nih.gov/123/'])[0]
            self.assertIn('Evidence coverage: full_text', result['content'])
            self.assertIn('PubMed PMID: 123', result['content'])
            self.assertEqual(req.call_count, 2)
            self.provider.extract(['https://pubmed.ncbi.nlm.nih.gov/123/'])
            self.assertEqual(req.call_count, 2)

    def test_fulltext_failure_keeps_abstract_with_limitation(self):
        with patch.object(self.provider, '_request', side_effect=[PUBMED, p.AccessError('Unavailable')]):
            result = self.provider.extract(['https://pubmed.ncbi.nlm.nih.gov/123/'])[0]
        self.assertIn('ABSTRACT ONLY', result['content'])
        self.assertIn('Human trial.', result['content'])
        self.assertIn('PMC full text unavailable', result['content'])

    def test_doi_conversion_matches_doi_not_first_record(self):
        response = {'records': [{'doi': '10.1234/other', 'pmcid': 'PMC999'},
                                {'doi': '10.1234/test', 'pmcid': 'PMC456'}]}
        with patch.object(self.provider, '_request', side_effect=[b'<eSearchResult><IdList/></eSearchResult>', json.dumps(response).encode(), bioc()]):
            result = self.provider.extract(['https://doi.org/10.1234/test'])[0]
        self.assertIn('PMC456', result['content'])

    def test_unknown_doi_uses_local_publisher_extraction(self):
        with patch.object(self.provider, '_api', side_effect=[b'<eSearchResult><IdList/></eSearchResult>', b'{"records": []}']), \
             patch.object(self.provider, '_local', return_value={'content': 'publisher'}) as local:
            result = self.provider.extract(['https://doi.org/10.1234/unknown'])[0]
        self.assertEqual(result['content'], 'publisher')
        local.assert_called_once()

    def test_doi_esearch_verifies_article_doi(self):
        with patch.object(self.provider, '_request', side_effect=[
            b'<eSearchResult><IdList><Id>123</Id></IdList></eSearchResult>', PUBMED, bioc()
        ]):
            result = self.provider.extract(['https://doi.org/10.1234/test'])[0]
        self.assertIn('Evidence coverage: full_text', result['content'])
        with patch.object(self.provider, '_api', return_value=PUBMED):
            with self.assertRaisesRegex(p.AccessError, 'DOI does not match'):
                self.provider._scholarly('pmid', '123', expected_doi='10.1234/wrong')

    def test_cookie_wall_is_error_not_successful_evidence(self):
        data = {'success': True, 'data': {'markdown': 'Cookies must be enabled\nEnable cookies for this site',
                                       'metadata': {'statusCode': 203}}}
        with patch.object(self.provider, '_request', return_value=json.dumps(data).encode()):
            result = self.provider.extract(['https://example.com'])[0]
        self.assertEqual(result['content'], '')
        self.assertIn('cookie_consent', result['error'])
        self.assertIsNone(p.challenge_reason('This research describes cookies. ' * 200))

    def test_ordinary_page_uses_loopback_no_hosted_client(self):
        data = {'success': True, 'data': {'markdown': '# Article\nUseful content', 'metadata': {}}}
        with patch.object(self.provider, '_request', return_value=json.dumps(data).encode()) as req:
            result = self.provider.extract(['https://example.com'])[0]
        self.assertIn('Useful content', result['content'])
        self.assertEqual(req.call_args.args[0], 'http://127.0.0.1:13002/v1/scrape')

    def test_hosted_configuration_fails_closed(self):
        with patch.object(self.provider, '_settings', return_value={'firecrawl_url': 'https://api.firecrawl.dev'}), \
             patch.object(self.provider, '_request') as req:
            result = self.provider.extract(['https://example.com'])[0]
        self.assertIn('hosted fallback is disabled', result['error'])
        req.assert_not_called()

    def test_policy_denial_prevents_requests(self):
        with patch.object(p, 'check_url', side_effect=p.AccessError('Website policy: blocked')), \
             patch.object(self.provider, '_request') as req:
            result = self.provider.extract(['https://pubmed.ncbi.nlm.nih.gov/123/'])[0]
        self.assertIn('Website policy', result['error'])
        req.assert_not_called()

    def test_redirected_scrape_destination_is_checked(self):
        data = {'success': True, 'data': {'markdown': 'Secret', 'metadata': {'sourceURL': 'http://127.0.0.1'}}}
        def check(url):
            if '127.0.0.1' in url:
                raise p.AccessError('Blocked private destination')
        with patch.object(p, 'check_url', side_effect=check), \
             patch.object(self.provider, '_request', return_value=json.dumps(data).encode()):
            result = self.provider.extract(['https://example.com'])[0]
        self.assertEqual(result['content'], '')
        self.assertIn('Blocked private', result['error'])

    def test_api_redirect_does_not_follow(self):
        with self.assertRaises(p.AccessError):
            p.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.test')

    def test_rate_limit_respects_retry_after_without_hammering(self):
        from urllib.error import HTTPError
        error = HTTPError(p.EUTILS, 429, 'limit', {'Retry-After': '120'}, None)
        with patch.object(p.urllib.request, 'build_opener') as opener, \
             patch.object(self.provider, '_pace'):
            opener.return_value.open.side_effect = error
            with self.assertRaisesRegex(p.AccessError, 'retry later'):
                self.provider._request(p.EUTILS + 'efetch.fcgi?id=123')
            self.assertEqual(opener.return_value.open.call_count, 1)


if __name__ == '__main__':
    unittest.main()
