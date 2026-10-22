"use client";

import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";

/** Keep source wording intact, with an explicit expansion for longer claims. */
export function ScannableText({ text, lines = 4, as: Tag = "p" }: {
  text: string;
  lines?: number;
  as?: "p" | "h3";
}) {
  const id = useId();
  const [expanded, setExpanded] = useState(false);
  const expandable = text.length > 240;
  return <div className="scannable-copy"><Tag id={id} className={expandable && !expanded ? "copy-clamped" : undefined}
    style={expandable && !expanded ? { WebkitLineClamp: lines } : undefined}>{text}</Tag>
    {expandable && <button type="button" aria-controls={id} aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>{expanded ? "Show less" : "Read more"}<ChevronDown size={11} style={{ transform: expanded ? "rotate(180deg)" : undefined }} /></button>}
  </div>;
}
