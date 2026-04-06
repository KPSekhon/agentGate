const API_BASE = "/api";

export async function fetchJson<T>(
  path: string,
  params?: Record<string, string>
): Promise<T> {
  const url = new URL(path, window.location.origin);
  url.pathname = `${API_BASE}${path}`;
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
