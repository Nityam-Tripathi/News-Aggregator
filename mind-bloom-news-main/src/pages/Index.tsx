import { useState, useEffect, useCallback } from "react";

const API = import.meta.env.VITE_API_URL; // NO trailing slash in .env

type Article = {
  title: string;
  url: string;
  image?: string;
  content?: string;
};

export default function Index() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [trending, setTrending] = useState<any[]>([]);
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<any[]>([]);

  // 🔥 Fetch Top News
  useEffect(() => {
    const fetchNews = async () => {
      try {
        const res = await fetch(`${API}/top-news`);

        if (!res.ok) {
          console.error("Top news API error:", res.status);
          return;
        }

        const data = await res.json();

        if (!Array.isArray(data)) {
          console.error("Invalid top-news response:", data);
          setArticles([]);
          return;
        }

        setArticles(data);
      } catch (err) {
        console.error("Fetch news error:", err);
      }
    };

    fetchNews();
  }, []);

  // 🔥 Fetch Trending
  useEffect(() => {
    const fetchTrending = async () => {
      try {
        const res = await fetch(`${API}/trending`);

        if (!res.ok) {
          console.error("Trending API error:", res.status);
          return;
        }

        const data = await res.json();

        if (!Array.isArray(data)) {
          console.error("Invalid trending response:", data);
          setTrending([]);
          return;
        }

        setTrending(data);
      } catch (err) {
        console.error("Trending fetch error:", err);
      }
    };

    fetchTrending();
  }, []);

  // 🔍 Ask (RAG)
  const handleSearch = useCallback(async (q: string) => {
    setQuery(q);

    try {
      const res = await fetch(`${API}/ask?query=${encodeURIComponent(q)}`);

      if (!res.ok) {
        console.error("Ask API error:", res.status);
        return;
      }

      const data = await res.json();

      setAnswer(data.answer || "");

      const safeSources = Array.isArray(data.sources) ? data.sources : [];
      setSources(safeSources);

    } catch (err) {
      console.error("Search error:", err);
    }
  }, []);

  return (
    <div style={{ padding: "20px" }}>

      <h1>🧠 AI News App</h1>

      {/* 🔍 Search */}
      <input
        type="text"
        placeholder="Search news..."
        onKeyDown={(e) => {
          if (e.key === "Enter") handleSearch((e.target as HTMLInputElement).value);
        }}
      />

      {/* 🧠 Answer */}
      {answer && (
        <div>
          <h2>Answer</h2>
          <p>{answer}</p>
        </div>
      )}

      {/* 📚 Sources */}
      {sources.length > 0 && (
        <div>
          <h2>Sources</h2>
          {(sources || []).map((s, i) => (
            <div key={i}>
              <a href={s.url} target="_blank">{s.title}</a>
            </div>
          ))}
        </div>
      )}

      {/* 🔥 Trending */}
      <h2>🔥 Trending</h2>
      <div>
        {(trending || []).map((t, i) => (
          <button key={i} onClick={() => handleSearch(t.topic)}>
            {t.topic} ({t.count})
          </button>
        ))}
      </div>

      {/* 📰 Top News */}
      <h2>📰 Top News</h2>
      <div>
        {(articles || []).map((a, i) => (
          <div key={i} style={{ marginBottom: "10px" }}>
            <a href={a.url} target="_blank">{a.title}</a>
          </div>
        ))}
      </div>

    </div>
  );
}