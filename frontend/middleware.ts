import { NextRequest, NextResponse } from 'next/server';

const PLATFORM_HOSTS = new Set(
  [
    'localhost',
    '127.0.0.1',
    'fibonatty.ru',
    'adm.fibonatty.ru',
    'www.fibonatty.ru',
  ].map((item) => item.toLowerCase())
);

const PUBLIC_CLIENT_PATH_PATTERNS = [
  /^\/$/,
  /^\/events\/?$/,
  /^\/events\/\d+\/?$/,
  /^\/products\/?$/,
  /^\/products\/\d+\/?$/,
  /^\/products\/\d+\/course\/?$/,
  /^\/products\/\d+\/course\/lessons\/\d+\/?$/,
  /^\/tasks\/?$/,
];

const isPlatformHost = (host: string): boolean => {
  if (PLATFORM_HOSTS.has(host)) {
    return true;
  }
  if (host.endsWith('.fibonatty.ru')) {
    return true;
  }
  if (host.endsWith('.localhost')) {
    return true;
  }
  return false;
};

const isPublicClientPath = (pathname: string): boolean => {
  return PUBLIC_CLIENT_PATH_PATTERNS.some((pattern) => pattern.test(pathname));
};

export function middleware(request: NextRequest) {
  const hostHeader = request.headers.get('host') || '';
  const host = hostHeader.split(':')[0]?.trim().toLowerCase() || '';
  const pathname = request.nextUrl.pathname;

  if (!host || isPlatformHost(host) || !isPublicClientPath(pathname)) {
    return NextResponse.next();
  }

  const headers = new Headers(request.headers);
  headers.set('x-custom-domain', host);

  const targetPath = pathname === '/' ? '/_custom-domain' : `/_custom-domain${pathname}`;
  const rewriteUrl = request.nextUrl.clone();
  rewriteUrl.pathname = targetPath;

  return NextResponse.rewrite(rewriteUrl, {
    request: {
      headers,
    },
  });
}

export const config = {
  matcher: '/:path*',
};
