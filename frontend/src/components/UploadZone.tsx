"use client";
/**
 * UploadZone.tsx — drag-and-drop box for résumés.
 *
 * The parent page does the real uploading and tells us how far it is through
 * `progress`. While busy we show the four stages a résumé goes through. The
 * stages advance on a timer to match what the server is really doing
 * (redact -> find evidence -> verify -> score); the last one waits for the
 * server's answer.
 */
import { useEffect, useState } from "react";
import { Icon } from "./Icon";

const STAGES = ["Hiding identity", "Finding evidence", "Verifying quotes", "Calculating score"];

export interface UploadProgress {
  current: number; // which file we're on (1-based)
  total: number;
  name: string;
}

interface Props {
  onFiles: (files: File[]) => void;
  progress: UploadProgress | null; // null = idle
}

export function UploadZone({ onFiles, progress }: Props) {
  const [dragging, setDragging] = useState(false);
  const [stage, setStage] = useState(0);
  const fileKey = progress ? progress.current : -1;

  // Restart the stage animation for every new file.
  useEffect(() => {
    if (fileKey < 0) return;
    setStage(0);
    const timer = window.setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 1100);
    return () => window.clearInterval(timer);
  }, [fileKey]);

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (progress) return;
    const files = Array.from(event.dataTransfer.files);
    if (files.length) onFiles(files);
  }

  return (
    <div
      className={`drop ${dragging ? "is-over" : ""} ${progress ? "is-busy" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      {!progress && (
        <input
          type="file"
          multiple
          accept=".pdf,.txt,.md,application/pdf,text/plain"
          aria-label="Upload résumés"
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            event.target.value = ""; // lets you pick the same file again later
            if (files.length) onFiles(files);
          }}
        />
      )}

      {progress ? (
        <>
          <p className="drop-title">
            Evaluating {progress.name}
            {progress.total > 1 && <span className="drop-count"> ({progress.current} of {progress.total})</span>}
          </p>
          <ol className="stages">
            {STAGES.map((label, index) => (
              <li key={label} className={index < stage ? "done" : index === stage ? "now" : ""}>
                <span className="stage-dot">{index < stage ? <Icon name="check" size={14} /> : <i />}</span>
                {label}
              </li>
            ))}
          </ol>
        </>
      ) : (
        <>
          <span className="drop-icon">
            <Icon name="upload" size={22} />
          </span>
          <p className="drop-title">Drop résumés here, or click to choose</p>
          <p className="drop-hint">PDF, TXT or Markdown, up to 10 MB each. You can add several at once.</p>
        </>
      )}
    </div>
  );
}
