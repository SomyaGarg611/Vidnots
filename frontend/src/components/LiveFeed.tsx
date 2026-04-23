import { useCallback, useEffect, useState } from "react";

export type LiveFrame = {
  ts: number;
  url: string;
  caption: string;
  is_slide: boolean;
};

type Props = {
  frames: LiveFrame[];
  apiUrl: string;
  running: boolean;
};

function fmtTs(ts: number): string {
  const s = Math.max(0, Math.floor(ts));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function rewrite(apiUrl: string, url: string): string {
  return url.startsWith("/frames/") ? apiUrl + url : url;
}

export function LiveFeed({ frames, apiUrl, running }: Props) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  const close = useCallback(() => setOpenIdx(null), []);
  const prev = useCallback(
    () => setOpenIdx((i) => (i === null ? null : Math.max(0, i - 1))),
    []
  );
  const next = useCallback(
    () =>
      setOpenIdx((i) =>
        i === null ? null : Math.min(frames.length - 1, i + 1)
      ),
    [frames.length]
  );

  useEffect(() => {
    if (openIdx === null) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "ArrowRight") next();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openIdx, close, prev, next]);

  if (frames.length === 0) return null;

  const open = openIdx !== null ? frames[openIdx] : null;

  return (
    <>
      <section className="live-feed">
        <header className="live-feed-head">
          <span className="live-dot" data-active={running} />
          <h3>
            Live feed
            <span className="live-count">
              {" "}
              · {frames.length} frame{frames.length === 1 ? "" : "s"}
            </span>
          </h3>
        </header>
        <div className="live-grid">
          {frames.map((f, i) => (
            <article
              key={`${f.ts}-${i}`}
              className={`live-card ${f.is_slide ? "slide" : ""}`}
              onClick={() => setOpenIdx(i)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setOpenIdx(i);
                }
              }}
              aria-label={`Open frame at ${fmtTs(f.ts)}`}
            >
              <div className="live-thumb-wrap">
                <img
                  className="live-thumb"
                  src={rewrite(apiUrl, f.url)}
                  alt={f.caption || `frame @ ${fmtTs(f.ts)}`}
                  loading="lazy"
                />
                <span className="live-ts">{fmtTs(f.ts)}</span>
                {f.is_slide && <span className="live-badge">SLIDE</span>}
              </div>
              <p className="live-caption">
                {f.caption || <em>(no caption)</em>}
              </p>
            </article>
          ))}
        </div>
      </section>

      {open && openIdx !== null && (
        <div className="lightbox" onClick={close} role="dialog" aria-modal="true">
          <button
            className="lightbox-close"
            onClick={(e) => {
              e.stopPropagation();
              close();
            }}
            aria-label="Close"
          >
            ×
          </button>

          {openIdx > 0 && (
            <button
              className="lightbox-nav prev"
              onClick={(e) => {
                e.stopPropagation();
                prev();
              }}
              aria-label="Previous frame"
            >
              ‹
            </button>
          )}
          {openIdx < frames.length - 1 && (
            <button
              className="lightbox-nav next"
              onClick={(e) => {
                e.stopPropagation();
                next();
              }}
              aria-label="Next frame"
            >
              ›
            </button>
          )}

          <figure
            className="lightbox-figure"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="lightbox-imgwrap">
              <img
                className="lightbox-img"
                src={rewrite(apiUrl, open.url)}
                alt={open.caption || `frame @ ${fmtTs(open.ts)}`}
              />
            </div>
            <figcaption className="lightbox-caption">
              <div className="lightbox-meta">
                <span className="lightbox-ts">{fmtTs(open.ts)}</span>
                {open.is_slide && <span className="live-badge">SLIDE</span>}
                <span className="lightbox-index">
                  {openIdx + 1} / {frames.length}
                </span>
              </div>
              <div className="lightbox-body">
                {open.caption ? (
                  <p>{open.caption}</p>
                ) : (
                  <p><em>(no caption)</em></p>
                )}
              </div>
            </figcaption>
          </figure>
        </div>
      )}
    </>
  );
}
