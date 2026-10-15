import { NextRequest } from 'next/server';

const api = process.env.API_BASE_URL || 'http://127.0.0.1:8010';

async function ingestProxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;

  // Only allow ingest routes
  if (path.length === 0 || path.some(part => !/^[a-zA-Z0-9_-]+$/.test(part))) {
    return new Response('Invalid route', { status: 400 });
  }

  const authHeader = request.headers.get('authorization');
  if (!authHeader) {
    return Response.json({ detail: 'Missing Authorization header' }, { status: 401 });
  }

  const headers = new Headers({
    'Content-Type': 'application/json',
    'Authorization': authHeader,
    'X-DynaGuard-Client': 'dashboard'
  });

  try {
    const body = await request.text();
    // 5MB limit
    if (body.length > 5 * 1024 * 1024) {
      return Response.json({ detail: 'Report payload exceeds 5 MB' }, { status: 413 });
    }

    const upstream = await fetch(`${api}/ingest/${path.join('/')}`, {
      method: 'POST',
      headers,
      body,
      cache: 'no-store',
      redirect: 'error',
      signal: AbortSignal.timeout(30000)
    });

    const resultText = await upstream.text();
    return new Response(resultText, {
      status: upstream.status,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }
    });
  } catch {
    return Response.json({ detail: 'DynaGuard ingestion service unavailable' }, { status: 503 });
  }
}

export const POST = ingestProxy;
