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
  <div style={{ display: "flex", height: "100vh", fontFamily: "Arial" }}>

    {/* Sidebar */}
    <div style={{
      width: "220px",
      background: "#111827",
      color: "white",
      padding: "20px"
    }}>
      <h2>🧠 NewsAI</h2>

      <p style={{ marginTop: "20px", color: "#9CA3AF" }}>Navigation</p>
      <p>🏠 Home</p>
      <p>🔥 Trending</p>

      <p style={{ marginTop: "20px", color: "#9CA3AF" }}>Categories</p>
      <p>AI</p>
      <p>Technology</p>
      <p>Business</p>
    </div>

    {/* Main Content */}
    <div style={{ flex: 1, padding: "20px", overflowY: "auto" }}>

      <h1>🧠 AI News App</h1>

      {/* Search */}
      <input
        type="text"
        placeholder="Search news..."
        style={{
          width: "100%",
          padding: "10px",
          marginBottom: "20px",
          borderRadius: "8px",
          border: "1px solid #ccc"
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleSearch((e.target as HTMLInputElement).value);
        }}
      />

      {/* Trending */}
      <h2>🔥 Trending</h2>
      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        {(trending || []).map((t, i) => (
          <button
            key={i}
            onClick={() => handleSearch(t.topic)}
            style={{
              padding: "6px 12px",
              borderRadius: "20px",
              border: "none",
              background: "#3B82F6",
              color: "white",
              cursor: "pointer"
            }}
          >
            {t.topic}
          </button>
        ))}
      </div>

      {/* Answer */}
      {answer && (
        <div style={{ marginTop: "20px" }}>
          <h2>🧠 Answer</h2>
          <p>{answer}</p>
        </div>
      )}

      {/* Sources */}
      {sources.length > 0 && (
        <div style={{ marginTop: "20px" }}>
          <h2>📚 Sources</h2>
          {(sources || []).map((s, i) => (
            <div key={i} style={{ marginBottom: "10px" }}>
              <a href={s.url} target="_blank" style={{ color: "#2563EB" }}>
                {s.title}
              </a>
            </div>
          ))}
        </div>
      )}

      {/* Top News */}
      <h2 style={{ marginTop: "30px" }}>📰 Top News</h2>

      <div style={{ display: "grid", gap: "15px" }}>
        {(articles || []).map((a, i) => (
          <div key={i} style={{
            border: "1px solid #ddd",
            borderRadius: "10px",
            padding: "15px",
            display: "flex",
            gap: "15px"
          }}>

            {/* Image */}
            {a.image && (
              <img
                src={a.image}
                alt=""
                style={{
                  width: "120px",
                  height: "80px",
                  objectFit: "cover",
                  borderRadius: "8px"
                }}
              />
            )}

            {/* Content */}
            <div>
              <a href={a.url} target="_blank" style={{
                fontWeight: "bold",
                color: "#111827"
              }}>
                {a.title}
              </a>

              <p style={{ fontSize: "14px", color: "#6B7280" }}>
                {a.content?.slice(0, 100)}...
              </p>
            </div>

          </div>
        ))}
      </div>

    </div>
  </div>
);
}