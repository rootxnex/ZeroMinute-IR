import ReactMarkdown from "react-markdown";

export function MarkdownViewer({ markdown }: { markdown: string }) {
  return (
    <div className="rounded-xl border border-zm-primary/30 bg-zm-bg/80 p-4">
      <div className="mb-2 border-l-2 border-zm-primary pl-2 text-xs uppercase tracking-wide text-zm-muted">
        Runbook Markdown
      </div>
      <article className="zm-markdown text-sm">
        <ReactMarkdown>{markdown}</ReactMarkdown>
      </article>
    </div>
  );
}
