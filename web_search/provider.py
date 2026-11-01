"""Bounded SearXNG JSON client: urllib CLI and cancellable HTTPX web transport."""
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.client import HTTPException
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urldefrag
from urllib.request import Request, urlopen

MAX_RESPONSE_BYTES = 1024 * 1024


class SearchError(ValueError):
    """User-facing provider failure, without response bodies or query echoes."""


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class SearchPage:
    query: str
    results: tuple
    fetched_at: str
    warnings: tuple = ()


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1
        elif tag in ('p', 'div', 'br'):
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value, limit):
    parser = _PlainText()
    parser.feed(value)
    parser.close()
    text = ''.join(parser.parts)
    text = ''.join(c if c.isprintable() or c.isspace() else ' ' for c in text)
    return ' '.join(text.split())[:limit]


def valid_url(value):
    if not isinstance(value, str) or not value or len(value) > 2048:
        return False
    if any(c.isspace() or not c.isprintable() for c in value):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port  # Validate malformed port values as well.
        return bool(parsed.scheme in ('http', 'https') and parsed.hostname
                    and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


class SearxSearch:
    def __init__(self, base_url, timeout=15, limit=5):
        if not valid_url(base_url):
            raise SearchError('Search URL must be an HTTP(S) URL without credentials.')
        parsed = urlsplit(base_url)
        if parsed.query or parsed.fragment:
            raise SearchError('Search URL must not contain a query or fragment.')
        if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or timeout <= 0:
            raise SearchError('Search timeout must be finite and positive.')
        if type(limit) is not int or not 1 <= limit <= 10:
            raise SearchError('Search result count must be between 1 and 10.')
        root = base_url.rstrip('/')
        self.endpoint = root if root.endswith('/search') else root + '/search'
        self.timeout = timeout
        self.limit = limit

    def search(self, query):
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise SearchError('Search query must contain 1 to 500 characters.')
        query = query.strip()
        request = Request(self.endpoint + '?' + urlencode({
            'q': query, 'format': 'json', 'categories': 'general',
        }), headers={'Accept': 'application/json', 'User-Agent': 'Sensai/1.0'})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            code = error.code
            error.close()
            if code == 403:
                raise SearchError('Search denied (403). Enable JSON format on the SearXNG instance.') from error
            if code == 429:
                raise SearchError('Search rate limit reached (429). Retry later.') from error
            raise SearchError(f'Search provider returned HTTP {code}.') from error
        except (URLError, OSError, HTTPException) as error:
            raise SearchError('Search unavailable: check the provider, network and timeout.') from error
        if len(raw) > MAX_RESPONSE_BYTES:
            raise SearchError('Search response exceeded the 1 MiB limit.')
        return self._parse_response(raw, query)

    async def search_async(self, query):
        """Cancellable web transport with an overall deadline and the same parser."""
        import asyncio
        import httpx
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise SearchError('Search query must contain 1 to 500 characters.')
        query = query.strip()

        async def receive():
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False,
                                         follow_redirects=False) as client:
                async with client.stream('GET', self.endpoint, params={
                    'q': query, 'format': 'json', 'categories': 'general',
                }, headers={'Accept': 'application/json', 'User-Agent': 'Sensai/1.0'}) as response:
                    if response.status_code == 403:
                        raise SearchError('Search denied (403). Enable JSON format on the SearXNG instance.')
                    if response.status_code == 429:
                        raise SearchError('Search rate limit reached (429). Retry later.')
                    if response.status_code != 200:
                        raise SearchError(f'Search provider returned HTTP {response.status_code}.')
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE_BYTES:
                            raise SearchError('Search response exceeded the 1 MiB limit.')
                        chunks.append(chunk)
                    return self._parse_response(b''.join(chunks), query)
        try:
            return await asyncio.wait_for(receive(), self.timeout)
        except (httpx.HTTPError, asyncio.TimeoutError) as error:
            raise SearchError('Search unavailable: check the provider, network and timeout.') from error

    def _parse_response(self, raw, query):
        try:
            data = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeError, RecursionError) as error:
            raise SearchError('Search provider did not return valid JSON.') from error
        if not isinstance(data, dict) or not isinstance(data.get('results'), list):
            raise SearchError('Search provider returned an invalid results list.')
        results = []
        seen = set()
        for item in data['results']:
            if not isinstance(item, dict) or not valid_url(item.get('url')):
                continue
            if not isinstance(item.get('title'), str) or not isinstance(item.get('content', ''), str):
                continue
            url = urldefrag(item['url'])[0]
            if url in seen:
                continue
            title = plain_text(item['title'], 200)
            if not title:
                continue
            seen.add(url)
            results.append(SearchResult(title, url, plain_text(item.get('content', ''), 1200)))
            if len(results) >= self.limit:
                break
        warnings = ()
        if data.get('unresponsive_engines'):
            warnings = ('Some search engines failed; results may be incomplete.',)
        if data['results'] and not results:
            raise SearchError('Search returned no usable result records.')
        if not results and warnings:
            raise SearchError('No results available; search engines reported failures.')
        return SearchPage(query, tuple(results), datetime.now(timezone.utc).isoformat(), warnings)
