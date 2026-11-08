// Vercel function: verifies the dashboard password, then dispatches the refresh.yml workflow.
import { timingSafeEqual } from "node:crypto";

export const OWNER = "zionge2k", REPO = "yt-ops", WORKFLOW = "refresh.yml", COOLDOWN_MS = 10 * 60 * 1000;
const DEFAULT_ORIGIN = "https://zionge2k.github.io";
const BASE = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}`;

function samePassword(given, expected) {
  const a = Buffer.from(given), b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

const ghHeaders = (token) => ({
  Authorization: `Bearer ${token}`,
  Accept: "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
  "User-Agent": "yt-ops-refresh",
});

export async function refresh({ body, env, fetchImpl = fetch, now = Date.now }) {
  if (!env.DASH_PASSWORD || !env.GITHUB_TOKEN) return { status: 500, json: { error: "server_not_configured" } };
  if (!body || typeof body !== "object" || typeof body.password !== "string" || !samePassword(body.password, env.DASH_PASSWORD)) {
    return { status: 401, json: { error: "wrong_password" } };
  }
  const headers = ghHeaders(env.GITHUB_TOKEN);

  // Stateless rate limit: the latest workflow_dispatch run is the only memory we need.
  let latest;
  try {
    const res = await fetchImpl(`${BASE}/runs?per_page=1&event=workflow_dispatch`, { headers });
    if (res.status !== 200) return { status: 502, json: { error: "github_unavailable" } };
    latest = ((await res.json()).workflow_runs || [])[0];
  } catch {
    return { status: 502, json: { error: "github_unavailable" } };
  }
  const t = now();
  const created = latest ? Date.parse(latest.created_at) : NaN;
  if (Number.isFinite(created) && t - created < COOLDOWN_MS) {
    return { status: 429, json: { error: "too_soon", retry_after_s: Math.ceil((COOLDOWN_MS - (t - created)) / 1000), started_at: latest.created_at } };
  }

  try {
    const res = await fetchImpl(`${BASE}/dispatches`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main" }),
    });
    if (res.status !== 204) return { status: 502, json: { error: "dispatch_failed", status: res.status } };
  } catch {
    return { status: 502, json: { error: "dispatch_failed", status: 0 } };
  }
  return { status: 202, json: { ok: true, started_at: new Date(t).toISOString() } };
}

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", process.env.ALLOWED_ORIGIN || DEFAULT_ORIGIN);
  res.setHeader("Vary", "Origin");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") return res.status(405).json({ error: "method_not_allowed" });
  let body = req.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch { body = null; }
  }
  const { status, json } = await refresh({ body, env: process.env });
  return res.status(status).json(json);
}
