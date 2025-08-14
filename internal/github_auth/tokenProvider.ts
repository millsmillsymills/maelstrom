/*
 Centralized GitHub token provider (TypeScript)
 Priority:
  1) OAuth2 refresh using pre-provisioned refresh token
  2) PAT from env (GITHUB_PAT or GITHUB_TOKEN)
 Includes simple in-memory cache and exponential backoff on probe.
 Scopes guidance: repo, workflow, read:org as required by use.
*/

import https from 'https';

type Token = {
  access_token: string;
  token_type: string;
  expires_at?: number;
  source: 'oauth' | 'pat' | 'env' | 'cache' | 'unknown';
  scopes?: string;
};

class TokenError extends Error {}

let memToken: Token | null = null;

function now(): number { return Date.now() / 1000; }

function getEnv(name: string): string | undefined {
  return process.env[name];
}

function httpsJson(options: https.RequestOptions, body?: any): Promise<any> {
  return new Promise((resolve, reject) => {
    const req = https.request({ ...options }, (res) => {
      const chunks: Buffer[] = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        try {
          const txt = Buffer.concat(chunks).toString('utf8');
          const json = txt ? JSON.parse(txt) : {};
          // Attach status
          (json as any)._status = res.statusCode;
          resolve(json);
        } catch (e) { reject(e); }
      });
    });
    req.on('error', reject);
    if (body) req.write(typeof body === 'string' ? body : JSON.stringify(body));
    req.end();
  });
}

async function oauthRefresh(cid: string, csec: string, rtok: string): Promise<Token> {
  const data = await httpsJson({
    method: 'POST',
    host: 'github.com',
    path: '/login/oauth/access_token',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    }
  }, { grant_type: 'refresh_token', refresh_token: rtok, client_id: cid, client_secret: csec });

  const access_token = data.access_token as string | undefined;
  if (!access_token) throw new TokenError('OAuth refresh failed: missing access_token');
  const expires_in = typeof data.expires_in === 'number' ? data.expires_in as number : undefined;
  const t: Token = {
    access_token,
    token_type: (data.token_type as string) || 'bearer',
    expires_at: expires_in ? now() + expires_in : undefined,
    source: 'oauth',
    scopes: (data.scope as string) || (data.scopes as string) || undefined,
  };
  memToken = t;
  return t;
}

async function probeToken(token: string): Promise<number> {
  const host = (getEnv('GITHUB_API_BASE') || 'https://api.github.com').replace('https://', '').replace('http://','');
  const path = '/rate_limit';
  const data = await httpsJson({
    method: 'GET',
    host,
    path,
    headers: {
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Authorization': `Bearer ${token}`
    }
  });
  return (data as any)._status ?? 0;
}

function backoff(attempt: number): Promise<void> {
  const base = Math.min(2 ** attempt, 16);
  const ms = 250 + Math.random() * base * 1000;
  return new Promise((r) => setTimeout(r, ms));
}

export async function getAccessToken(): Promise<Token> {
  if (memToken && (!memToken.expires_at || memToken.expires_at - now() > 300)) {
    const code = await probeToken(memToken.access_token).catch(() => 0);
    if (code === 200 || code === 304) return memToken;
  }

  const cid = getEnv('GITHUB_OAUTH_CLIENT_ID');
  const csec = getEnv('GITHUB_OAUTH_CLIENT_SECRET');
  const rtok = getEnv('GITHUB_OAUTH_REFRESH_TOKEN');
  if (cid && csec && rtok) {
    try {
      const t = await oauthRefresh(cid, csec, rtok);
      for (let i = 0; i < 3; i++) {
        const code = await probeToken(t.access_token).catch(() => 0);
        if (code === 200 || code === 304) return t;
        if ([401,403,429,0].includes(code)) await backoff(i); else break;
      }
    } catch (e) {
      // fall through to PAT
    }
  }

  const pat = getEnv('GITHUB_PAT') || getEnv('GITHUB_TOKEN');
  if (pat) {
    const t: Token = { access_token: pat, token_type: 'bearer', source: 'pat' };
    for (let i = 0; i < 3; i++) {
      const code = await probeToken(t.access_token).catch(() => 0);
      if (code === 200 || code === 304) return t;
      if ([401,403,429,0].includes(code)) await backoff(i); else break;
    }
  }

  throw new TokenError('Unable to obtain GitHub token. Set OAuth env or GITHUB_PAT/GITHUB_TOKEN.');
}

export default { getAccessToken };
