import { NextRequest } from 'next/server';

const api = process.env.API_BASE_URL || 'http://127.0.0.1:8010';

async function proxy(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  const { path } = await context.params;
  if (path.some(part => !/^[a-zA-Z0-9_-]+$/.test(part))) return new Response('Invalid route', {status: 400});
  if (request.method !== 'GET') {
    if (request.headers.get('x-dynaguard-client') !== 'dashboard' || request.headers.get('sec-fetch-site') === 'cross-site') {
      return Response.json({detail: 'Cross-site request blocked'}, {status: 403});
    }
    const origin = request.headers.get('origin');
    if (origin) {
      const originHost = new URL(origin).host.toLowerCase();
      const host = (request.headers.get('host') || '').toLowerCase();
      const forwardedHost = (request.headers.get('x-forwarded-host') || '').toLowerCase();
      const originName = originHost.split(':')[0];
      const hostName = host.split(':')[0];
      const forwardedName = forwardedHost.split(':')[0];

      const isAllowed =
        originHost === host ||
        originHost === forwardedHost ||
        originName === hostName ||
        originName === forwardedName ||
        hostName === '127.0.0.1' ||
        hostName === 'localhost';

      if (!isAllowed) {
        return Response.json({detail: 'Invalid origin'}, {status: 403});
      }
    }
  }
  const headers = new Headers({'Content-Type': 'application/json', 'X-DynaGuard-Client': 'dashboard'});
  const cookie = request.headers.get('cookie');
  if (cookie) headers.set('cookie', cookie);
  try {
    const body = request.method === 'GET' ? undefined : await request.text();
    if (body && body.length > 8192) return Response.json({detail: 'Request too large'}, {status: 413});
    const upstream = await fetch(`${api}/${path.join('/')}`, {method: request.method, headers, body, cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(10000)});
    const resultHeaders = new Headers({'Content-Type': 'application/json', 'Cache-Control': 'no-store'});
    const session = upstream.headers.get('set-cookie');
    if (session) resultHeaders.set('set-cookie', session);
    return new Response(await upstream.text(), {status: upstream.status, headers: resultHeaders});
  } catch {
    return Response.json({detail: 'Control plane unavailable'}, {status: 503});
  }
}

export const GET = proxy;
export const POST = proxy;
