const KEY = "vidnots.cache.v1";
const MAX = 10;

export type CachedJob = {
  url: string;
  provider: string;
  model: string;
  notes: string;
  at: number;
};

export function loadCache(): CachedJob[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function saveToCache(entry: CachedJob): void {
  const existing = loadCache().filter((e) => e.url !== entry.url);
  const next = [entry, ...existing].slice(0, MAX);
  localStorage.setItem(KEY, JSON.stringify(next));
}

export function getCached(url: string): CachedJob | undefined {
  return loadCache().find((e) => e.url === url);
}
