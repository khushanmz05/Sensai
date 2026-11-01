"""HTTP contract, strict deadline and cancellation for browser search."""
import asyncio
import json
import unittest
from unittest.mock import patch

import httpx
from web_search import SearxSearch, SearchError
from web_search.provider import MAX_RESPONSE_BYTES


class AsyncSearchTests(unittest.IsolatedAsyncioTestCase):
    def client(self, handler):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return patch('httpx.AsyncClient', return_value=client)

    async def test_only_query_sent_and_same_parser_bounds_sources(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={'results': [
                {'title': '<b>Python</b>', 'url': 'https://python.org/#one', 'content': 'Docs'},
                {'title': 'Duplicate', 'url': 'https://python.org/#two'},
                {'title': 'Bad', 'url': 'javascript:alert(1)'},
            ]})
        with self.client(handler):
            page = await SearxSearch('http://search.test').search_async('Python & asyncio')
        self.assertEqual(len(page.results), 1)
        self.assertEqual(page.results[0].title, 'Python')
        self.assertEqual(page.results[0].url, 'https://python.org/')
        self.assertEqual(dict(requests[0].url.params), {'q': 'Python & asyncio', 'format': 'json', 'categories': 'general'})
        self.assertEqual(requests[0].content, b'')

    async def test_invalid_query_has_no_network_effect(self):
        with patch('httpx.AsyncClient') as client:
            for query in ('', ' ', None, 'x' * 501):
                with self.assertRaises(SearchError):
                    await SearxSearch('http://search.test').search_async(query)
        client.assert_not_called()

    async def test_provider_errors_json_size_and_redirects_fail_closed(self):
        cases = [(httpx.Response(code, text='private echoed query'), text) for code, text in
                 [(403, 'Enable JSON'), (429, 'rate limit'), (302, 'HTTP 302'), (500, 'HTTP 500')]]
        cases += [(httpx.Response(200, text='<html>private CAPTCHA</html>'), 'valid JSON'),
                  (httpx.Response(200, json={'results': None}), 'invalid results'),
                  (httpx.Response(200, content=b'x' * (MAX_RESPONSE_BYTES + 1)), '1 MiB')]
        for response, expected in cases:
            with self.subTest(expected=expected), self.client(lambda request: response):
                with self.assertRaisesRegex(SearchError, expected) as caught:
                    await SearxSearch('http://search.test').search_async('query')
                self.assertNotIn('private', str(caught.exception))

    async def test_total_deadline_and_cancel_close_stream(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                started, closed = asyncio.Event(), asyncio.Event()
                class SlowStream(httpx.AsyncByteStream):
                    async def __aiter__(self):
                        started.set()
                        while True:
                            yield b' '
                            await asyncio.sleep(0.01)
                    async def aclose(self):
                        closed.set()
                with self.client(lambda request: httpx.Response(200, stream=SlowStream())):
                    task = asyncio.create_task(SearxSearch('http://search.test', timeout=0.04).search_async('query'))
                    await started.wait()
                    if cancel:
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                    else:
                        with self.assertRaisesRegex(SearchError, 'unavailable'):
                            await asyncio.wait_for(task, 1)
                self.assertTrue(closed.is_set())
