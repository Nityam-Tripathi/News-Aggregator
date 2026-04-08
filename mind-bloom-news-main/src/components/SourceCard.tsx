import { ExternalLink, FileText } from "lucide-react";
import { motion } from "framer-motion";
import type { SourceReference } from "@/data/mockData";

interface SourceCardProps {
  source: SourceReference;
  index: number;
}

const SourceCard = ({ source, index }: SourceCardProps) => (
  <motion.a
    href={source.url}
    target="_blank"
    rel="noopener noreferrer"
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: index * 0.05 }}
    className="group flex items-start gap-3 p-4 bg-card border border-border rounded-xl hover:shadow-md hover:border-primary/20 transition-all"
  >
    <div className="p-2 rounded-lg bg-muted shrink-0">
      <FileText size={14} className="text-muted-foreground" />
    </div>
    <div className="flex-1 min-w-0">
      <p className="text-sm font-medium leading-snug line-clamp-2 group-hover:text-primary transition-colors">{source.title}</p>
      <div className="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground">
        <span className="font-medium">{source.source}</span>
        <span>·</span>
        <span>{source.publishDate}</span>
      </div>
    </div>
    <ExternalLink size={14} className="shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity mt-1" />
  </motion.a>
);

export default SourceCard;
