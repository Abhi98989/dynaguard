"""Bounded HTTP(S) transport shared by verification and browser discovery."""
import asyncio
import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit
import httpx
from .config import safe_path


class Incomplete(Exception):
    pass


class Budget:
    def __init__(self, limits):
        self.limits = limits
        self.deadline = time.monotonic() + limits.seconds
        self.count = 0

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Incomplete('Run deadline reached')
        return remaining

    def claim(self):
        self.remaining()
        if self.count >= self.limits.requests:
            raise Incomplete('Run request limit reached')
        self.count += 1


class ScopedHTTP:
    def __init__(self, target, budget, transport=None):
        self.target, self.budget = target, budget
        self.client = httpx.AsyncClient(follow_redirects=False, trust_env=False, timeout=5, transport=transport)
        self.headers = {}
        self.cookies = httpx.Cookies()

    def validate(self, url):
        p, root = urlsplit(url), urlsplit(self.target.origin)
        port = lambda v: v.port or (443 if v.scheme == 'https' else 80)
        if (p.scheme, p.hostname, port(p)) != (root.scheme, root.hostname, port(root)) or p.username or p.password or p.fragment:
            raise Incomplete('Request blocked outside configured origin')
        try:
            safe_path(p.path or '/')
        except ValueError:
            raise Incomplete('Ambiguous request path blocked') from None
        if not any(p.path == allowed or (allowed.endswith('/') and p.path.startswith(allowed)) for allowed in self.target.allowed_paths):
            raise Incomplete('Request path is outside configured scope')
        return p, port(p)

    async def request(self, method, path, json=None):
        url = urljoin(self.target.origin + '/', path)
        if method not in ('GET', 'HEAD', 'POST'):
            raise Incomplete('Unsupported HTTP method')
        for _ in range(5):
            p, port = self.validate(url)
            try:
                answers = await asyncio.wait_for(asyncio.to_thread(socket.getaddrinfo, p.hostname, port, 0, socket.SOCK_STREAM), timeout=min(5, self.budget.remaining()))
                addresses = {str(ipaddress.ip_address(item[4][0])) for item in answers}
                allowed = {str(ipaddress.ip_address(ip)) for ip in self.target.pinned_ips}
                if not addresses or not addresses.issubset(allowed):
                    raise Incomplete('DNS addresses differ from configured pins')
                address = sorted(addresses)[0]
                address = f'[{address}]' if ':' in address else address
                wire = f'{p.scheme}://{address}:{port}{p.path or "/"}' + (f'?{p.query}' if p.query else '')
                self.budget.claim()
                outgoing = httpx.Request(method, url, headers=self.headers)
                self.cookies.set_cookie_header(outgoing)
                self.client.cookies.clear()
                async with asyncio.timeout(min(5, self.budget.remaining())):
                    async with self.client.stream(method, wire, json=json, headers={**{k: v for k, v in outgoing.headers.items() if k not in ('host', 'content-length')}, 'host': p.netloc}, extensions={'sni_hostname': p.hostname}) as response:
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > self.budget.limits.response_bytes:
                                raise Incomplete('Response body exceeded configured limit')
                        result = httpx.Response(response.status_code, headers=response.headers, content=bytes(data), request=httpx.Request(method, url))
                        self.cookies.extract_cookies(result)
            except (httpx.HTTPError, OSError, TimeoutError):
                raise Incomplete('Target unavailable, TLS verification failed, or request timed out') from None
            if result.is_redirect:
                if method not in ('GET', 'HEAD'):
                    raise Incomplete('Login redirects are not supported by JSON login')
                location = result.headers.get('location')
                if not location:
                    raise Incomplete('Redirect lacks destination')
                url = urljoin(url, location)
                self.validate(url)
                continue
            return result
        raise Incomplete('Redirect limit reached')

    async def close(self):
        await self.client.aclose()
