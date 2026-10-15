"""Optional browser navigation through the same scoped HTTP transport."""
import os
from urllib.parse import urljoin, urlsplit
from .engine import Session, report_base, mask
from .network import Budget, Incomplete
from .source import inspect_text


async def discover(config, progress=None):
    result = report_base('discover', config.project)
    result.update(build_id=config.build_id, target=config.target.origin, pages=[], requests=[])
    result['limitations'] = ['Read-only browser discovery; no clicks, form submissions, WebSockets or service workers.', 'Blocked assets and write requests may prevent complete rendering.', 'Only explicitly configured pages are navigated; discovered links are listed, not followed.', 'Browser interception is not an OS sandbox. Run untrusted pages in a dedicated network-restricted runner.']
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        result.update(status='incomplete', reason='Install dynaguard[browser] and Chromium to use discovery')
        return result
    budget, secrets = Budget(config.limits), []
    name = config.discovery_identity or next(iter(config.identities))
    session = Session(config.identities[name], config.target, budget, secrets)
    blocked = 0
    try:
        await session.login()
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=os.environ.get('DYNAGUARD_CHROMIUM_EXECUTABLE') or None)
            try:
                context = await browser.new_context(service_workers='block', accept_downloads=False)
                await context.route_web_socket('**/*', lambda ws: ws.close())

                async def route_request(route):
                    nonlocal blocked
                    request = route.request
                    # Record path only, never request headers, body or query values.
                    entry = {'method': request.method, 'path': urlsplit(request.url).path, 'type': request.resource_type}
                    try:
                        if request.method not in ('GET', 'HEAD'):
                            raise Incomplete('State-changing request blocked during discovery')
                        session.http.validate(request.url)
                        response = await session.http.request(request.method, request.url)
                        headers = {k: v for k, v in response.headers.items() if k.lower() not in ('content-encoding', 'content-length', 'transfer-encoding', 'set-cookie')}
                        await route.fulfill(status=response.status_code, headers=headers, body=response.content)
                        entry['status'] = response.status_code
                        if any(t in response.headers.get('content-type', '') for t in ('text/', 'javascript', 'json')):
                            findings = inspect_text(response.text, urlsplit(request.url).path)
                            known = {f['id'] for f in result['findings']}
                            result['findings'].extend(f for f in findings if f['id'] not in known)
                            if len(result['findings']) >= 1000:
                                result['findings'] = result['findings'][:1000]
                                raise Incomplete('Finding limit reached')
                    except Incomplete as error:
                        blocked += 1
                        entry['blocked'] = str(error)
                        await route.abort()
                    result['requests'].append(entry)

                await context.route('**/*', route_request)
                page = await context.new_page()
                for path in config.discovery_paths[:config.limits.pages]:
                    if progress:
                        await progress('Rendering configured page')
                    session.http.validate(urljoin(config.target.origin + '/', path))
                    await page.goto(config.target.origin + path, wait_until='networkidle', timeout=min(15000, budget.remaining() * 1000))
                    links = await page.locator('a[href]').evaluate_all('(nodes) => nodes.map(n => n.href)')
                    # Strip query/fragment values; do not persist page content or titles containing personal data.
                    result['pages'].append({'path': path.split('?')[0], 'links': sorted({urlsplit(link).path for link in links if urlsplit(link).netloc == urlsplit(config.target.origin).netloc})[:200]})
                await session.check()
            finally:
                await browser.close()
    except Incomplete as error:
        result.update(status='incomplete', reason=str(error))
    except Exception:
        result.update(status='incomplete', reason='Browser unavailable, navigation failed, or execution interrupted; raw exception omitted')
    finally:
        await session.http.close()
    if blocked or not config.discovery_paths or len(config.discovery_paths) > config.limits.pages:
        result['status'] = 'incomplete'
    result['coverage'] = {'planned_pages': len(config.discovery_paths), 'rendered_pages': len(result['pages']), 'requests': budget.count, 'blocked_requests': blocked}
    return mask(result, secrets)
