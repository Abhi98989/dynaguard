import asyncio
import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit
import httpx
from .config import targets


class Incomplete(Exception):
    pass


class ScopedClient:
    """Only HTTP fixture origins. Connect to a validated IP, never re-resolve at send time."""
    def __init__(self, origin, request_limit, timeout_seconds, transport=None):
        self.origin = origin
        self.limit = request_limit
        self.deadline = time.monotonic() + timeout_seconds
        self.count = 0
        self.client = httpx.AsyncClient(follow_redirects=False, trust_env=False, timeout=3, transport=transport)

    async def close(self):
        await self.client.aclose()

    async def destination(self, url):
        parsed = urlsplit(url)
        root = urlsplit(self.origin)
        if (parsed.scheme, parsed.hostname, parsed.port or 80) != (root.scheme, root.hostname, root.port or 80):
            raise Incomplete('Scope blocked: request or redirect outside the exact allowed origin')
        if parsed.username or parsed.password or parsed.fragment or parsed.scheme != 'http' or self.origin not in targets():
            raise Incomplete('Scope blocked: invalid or unregistered fixture origin')
        if parsed.query or parsed.path not in {'/login', '/records/record-a', '/records/record-b'}:
            raise Incomplete('Scope blocked: path is outside the designated fixture endpoints')
        allowed = targets()[self.origin]
        # DNS is checked each request; the actual connection uses the checked address.
        try:
            addresses = {item[4][0] for item in await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, parsed.port or 80, socket.AF_INET, socket.SOCK_STREAM)}
        except OSError:
            raise Incomplete('Target DNS unavailable') from None
        if not addresses or not addresses.issubset(set(allowed)):
            raise Incomplete('Scope blocked: resolved address is not pinned by deployment configuration')
        address = sorted(addresses)[0]
        if ipaddress.ip_address(address).is_link_local:
            raise Incomplete('Scope blocked: link-local addresses are prohibited')
        return f'http://{address}:{parsed.port or 80}{parsed.path}', parsed.netloc

    async def request(self, method, path, **kwargs):
        url = urljoin(self.origin + '/', path)
        for _ in range(4):
            if self.count >= self.limit:
                raise Incomplete('Request limit reached')
            if time.monotonic() >= self.deadline:
                raise Incomplete('Test deadline exceeded')
            wire_url, host = await self.destination(url)
            self.count += 1
            headers = dict(kwargs.pop('headers', {}))
            headers['Host'] = host
            # Bound both total duration and body size, including streamed responses.
            try:
                async with asyncio.timeout(min(3, max(0.01, self.deadline - time.monotonic()))):
                    async with self.client.stream(method, wire_url, headers=headers, **kwargs) as response:
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > 16384:
                                raise Incomplete('Response exceeded evidence size limit')
                        result = httpx.Response(response.status_code, headers=response.headers, content=bytes(data))
            except (httpx.HTTPError, TimeoutError):
                raise Incomplete('Target unavailable or request timed out') from None
            if result.is_redirect:
                location = result.headers.get('location')
                if not location:
                    raise Incomplete('Redirect missing destination')
                url = urljoin(url, location)
                # Validate before any subsequent request, including credentials.
                await self.destination(url)
                if method != 'GET':
                    raise Incomplete('Login redirects are not supported')
                kwargs['headers'] = headers
                continue
            return result
        raise Incomplete('Redirect limit reached')
