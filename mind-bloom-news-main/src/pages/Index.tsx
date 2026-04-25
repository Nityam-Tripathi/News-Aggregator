import { useState, useCallback, useEffect } from "react";
import { TrendingUp, BookOpen, Clock } from "lucide-react";
import SearchBar from "@/components/SearchBar";
import AnswerSection from "@/components/AnswerSection";
import SourceCard from "@/components/SourceCard";
import NewsCard from "@/components/NewsCard";
import ErrorMessage from "@/components/ErrorMessage";
import { AnswerSkeleton, SourceSkeleton } from "@/components/SkeletonLoaders";

type NewsArticle = {
  id: string;
  title: string;
  url: string;
  description?: string;
  image?: string;
  published_at?: string; // ✅ NEW
  bookmarked?: boolean;
};const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const Index = () => {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [analyticsData, setAnalyticsData] = useState<any[]>([]);
  const [searchState, setSearchState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [currentQuery, setCurrentQuery] = useState("");

  const [answer, setAnswer] = useState("");
  const [displayedAnswer, setDisplayedAnswer] = useState("");
  const [sources, setSources] = useState<any[]>([]);

  // 🕒 Format Date
  const formatDate = (date?: string) => {
    if (!date) return "";
    return new Date(date).toLocaleString();
  };

  // 🔥 Fetch Trending News
  useEffect(() => {
    const fetchNews = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/top-news`);
        const data = await res.json();

        const formatted = data.map((item: any, index: number) => ({
          id: index.toString(),
          title: item.title,
          url: item.url,
          description: item.content || "Click to read full article",
          image: item.image || "",
          published_at: item.published_at, // ✅ NEW
          bookmarked: false,
        }));

        setArticles(formatted);
      } catch (error) {
        console.error("Failed to fetch news", error);
      }
    };

    fetchNews();
  }, []);

  // 🔥 Fetch Analytics
  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/analytics`);
        const data = await res.json();
        setAnalyticsData(data);
      } catch (error) {
        console.error("Analytics fetch error:", error);
      }
    };

    fetchAnalytics();
  }, []);

  // 🧠 Keywords
  const getTopKeywords = () => {
    const text = analyticsData.map((a) => a.title + " " + a.content).join(" ");
    const words = text.toLowerCase().split(/\W+/);

    const freq: any = {};
    words.forEach((w) => {
      if (w.length > 4) freq[w] = (freq[w] || 0) + 1;
    });

    return Object.entries(freq)
      .sort((a: any, b: any) => b[1] - a[1])
      .slice(0, 6);
  };

  // 🔥 Search
  const handleSearch = useCallback(async (query: string) => {
    setCurrentQuery(query);
    setSearchState("loading");

    try {
      const res = await fetch(
        `${API_BASE_URL}/ask?query=${encodeURIComponent(query)}`
      );

      const data = await res.json();

      const fullAnswer = data.answer || "";

      setAnswer(fullAnswer);
      setDisplayedAnswer("");

      let i = 0;
      const interval = setInterval(() => {
        i++;
        setDisplayedAnswer(fullAnswer.slice(0, i));
        if (i >= fullAnswer.length) clearInterval(interval);
      }, 15);

      const formattedSources = (data.sources || []).map((s: any) => ({
        ...s,
        image_url: s.image,
        published_at: s.published_at, // ✅ NEW
      }));

      setSources(formattedSources);
      setSearchState("done");

    } catch (error) {
      console.error("API ERROR:", error);
      setSearchState("error");
    }
  }, []);

  const handleBookmark = useCallback((id: string) => {
    setArticles((prev) =>
      prev.map((a) =>
        a.id === id ? { ...a, bookmarked: !a.bookmarked } : a
      )
    );
  }, []);

  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className={`transition-all duration-500 ${searchState === "idle" ? "pt-24 pb-16" : "pt-8 pb-6"}`}>
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-3">
            News<span className="text-primary">AI</span>
          </h1>

          <SearchBar
            onSearch={handleSearch}
            isLoading={searchState === "loading"}
            large={searchState === "idle"}
          />
        </div>
      </section>

      <div className="max-w-6xl mx-auto px-4 pb-16 space-y-10">

        {/* Loading */}
        {searchState === "loading" && (
          <div className="space-y-6">
            <AnswerSkeleton />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[0, 1, 2, 3].map((i) => <SourceSkeleton key={i} />)}
            </div>
          </div>
        )}

        {/* Answer */}
        {searchState === "done" && (
          <div className="space-y-6">
            <AnswerSection answer={displayedAnswer} query={currentQuery} />

            <div>
              <div className="flex items-center gap-2 mb-3">
                <BookOpen size={16} />
                <h2 className="text-sm font-semibold uppercase">Sources</h2>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {sources.map((s, i) => (
                  <div key={i} className="bg-white p-3 rounded shadow">
                    <SourceCard source={s} index={i} />

                    {/* 🕒 Source time */}
                    <div className="flex items-center gap-1 text-xs text-gray-500 mt-1">
                      <Clock size={12} />
                      {formatDate(s.published_at)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {searchState === "error" && <ErrorMessage />}

        {/* Trending */}
        <section>
          <div className="flex items-center gap-2 mb-6">
            <TrendingUp size={20} />
            <h2 className="text-xl font-bold">Trending News</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {articles.map((article, i) => (
              <div key={article.id} className="relative">
                <NewsCard
                  article={article}
                  index={i}
                  onBookmark={handleBookmark}
                />

                {/* 🕒 Trending time */}
                <div className="absolute bottom-2 left-2 flex items-center gap-1 text-xs bg-white/80 px-2 py-1 rounded">
                  <Clock size={12} />
                  {formatDate(article.published_at)}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Analytics */}
        <section>
          <h2 className="text-xl font-bold mb-4">📊 News Analytics</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-xl shadow">
              <h3 className="text-sm text-muted-foreground">Total Articles</h3>
              <p className="text-2xl font-bold">{analyticsData.length}</p>
            </div>

            <div className="bg-white p-4 rounded-xl shadow col-span-2">
              <h3 className="text-sm text-muted-foreground mb-2">Top Keywords</h3>
              <div className="flex flex-wrap gap-2">
                {getTopKeywords().map(([word, count]: any, i: number) => (
                  <span
                    key={i}
                    className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm"
                  >
                    {word} ({count})
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
};

export default Index;