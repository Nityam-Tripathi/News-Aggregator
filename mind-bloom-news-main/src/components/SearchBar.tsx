import { useState, useRef, useEffect } from "react";
import { Search, X, Clock } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { recentSearches } from "@/data/mockData";

interface SearchBarProps {
  onSearch: (query: string) => void;
  isLoading?: boolean;
  large?: boolean;
}

const SearchBar = ({ onSearch, isLoading, large }: SearchBarProps) => {
  const [query, setQuery] = useState("");
  const [showRecent, setShowRecent] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowRecent(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
      setShowRecent(false);
    }
  };

  const handleRecentClick = (search: string) => {
    setQuery(search);
    onSearch(search);
    setShowRecent(false);
  };

  return (
    <div ref={wrapperRef} className="relative w-full max-w-2xl mx-auto">
      <form onSubmit={handleSubmit}>
        <div className={`relative flex items-center rounded-2xl border border-border bg-card shadow-sm transition-shadow focus-within:shadow-md focus-within:border-primary/30 ${large ? "px-5 py-4" : "px-4 py-3"}`}>
          <Search className="shrink-0 text-muted-foreground" size={large ? 22 : 18} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setShowRecent(true)}
            placeholder="Ask anything about latest news..."
            className={`flex-1 bg-transparent outline-none placeholder:text-muted-foreground ml-3 ${large ? "text-lg" : "text-sm"}`}
          />
          {query && (
            <button type="button" onClick={() => setQuery("")} className="p-1 rounded-full hover:bg-muted transition-colors">
              <X size={16} className="text-muted-foreground" />
            </button>
          )}
          {isLoading ? (
            <div className="ml-2 flex gap-1">
              {[0, 1, 2].map((i) => (
                <span key={i} className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse-dot" style={{ animationDelay: `${i * 0.2}s` }} />
              ))}
            </div>
          ) : (
            <button type="submit" className="ml-2 px-4 py-1.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity">
              Search
            </button>
          )}
        </div>
      </form>

      <AnimatePresence>
        {showRecent && !query && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="absolute z-50 top-full mt-2 w-full bg-card border border-border rounded-xl shadow-lg overflow-hidden"
          >
            <div className="px-4 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">Recent Searches</div>
            {recentSearches.map((s) => (
              <button key={s} onClick={() => handleRecentClick(s)} className="flex items-center gap-3 w-full px-4 py-2.5 hover:bg-muted/60 transition-colors text-sm text-left">
                <Clock size={14} className="text-muted-foreground shrink-0" />
                <span>{s}</span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default SearchBar;
