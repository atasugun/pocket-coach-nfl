import { useEffect, useState } from "react";
import { api } from "../api";
import type { Limitations } from "../types";
import "./LimitationsNote.css";

export default function LimitationsLink() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Limitations | null>(null);

  useEffect(() => {
    if (open && !data) {
      api.limitations().then(setData).catch(() => setData(null));
    }
  }, [open, data]);

  return (
    <>
      <button className="limitations-link" onClick={() => setOpen(true)}>
        What this tool can't tell you
      </button>
      {open && (
        <div className="limitations-backdrop" onClick={() => setOpen(false)}>
          <div className="limitations-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <h2>{data?.title ?? "What this tool can't tell you"}</h2>
            <ul>
              {(data?.bullets ?? []).map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
            <button className="limitations-close" onClick={() => setOpen(false)}>
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}
