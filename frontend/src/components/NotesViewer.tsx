import Markdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

type Props = { markdown: string; apiUrl: string };

// Rewrite frame URLs from the event stream (relative paths like
// "/frames/<job>/<file>") so the browser loads them from the api origin.
function rewriteImageUrl(apiUrl: string, src: string | undefined): string {
  if (!src) return "";
  if (src.startsWith("/frames/")) return apiUrl + src;
  return src;
}

export function NotesViewer({ markdown, apiUrl }: Props) {
  return (
    <div className="notes">
      <Markdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          img: ({ src, alt }) => (
            <img src={rewriteImageUrl(apiUrl, src as string)} alt={alt ?? ""} loading="lazy" />
          ),
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {markdown}
      </Markdown>
    </div>
  );
}
