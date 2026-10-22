import Link from "next/link";
import { ArrowUpRight, Layers3, Plus } from "lucide-react";

export function NewsHeader({ onUpload, story = false }: { onUpload: () => void; story?: boolean }) {
  return (
    <header className="news-header">
      <Link href="/" className="news-brand" aria-label="Folio home"><Layers3 size={27} strokeWidth={1.6} />folio<span>.</span></Link>
      <nav aria-label="Main navigation"><Link href="/" aria-current={!story ? "page" : undefined}>The briefing</Link>{story && <span className="nav-story"> / Story room</span>}</nav>
      <button className="news-button" onClick={onUpload}><Plus size={16} /> Upload report <ArrowUpRight size={14} className="max-sm:hidden" /></button>
    </header>
  );
}
