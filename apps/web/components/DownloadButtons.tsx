export function DownloadButtons({ markdown }: { markdown: string }) {
  const downloadMd = () => {
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "zerominute-runbook.md";
    a.click();
    URL.revokeObjectURL(url);
  };

  const printPdf = () => window.print();

  return (
    <div className="flex gap-3">
      <button
        onClick={downloadMd}
        className="rounded-lg border border-zm-primary/50 bg-zm-surface2 px-4 py-2 text-sm text-zm-text transition hover:shadow-zm-glow"
      >
        Download Markdown
      </button>
      <button
        onClick={printPdf}
        className="rounded-lg bg-zm-primary px-4 py-2 text-sm font-semibold text-zm-bg transition hover:brightness-110"
      >
        Download PDF
      </button>
    </div>
  );
}
