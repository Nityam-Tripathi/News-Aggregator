import { Bookmark } from "lucide-react";

const NewsCard = ({ article, index, onBookmark }: any) => {
  return (
    <div
      className="group rounded-2xl overflow-hidden shadow-md hover:shadow-xl transition-all duration-300 bg-white cursor-pointer"
      onClick={() => window.open(article.url, "_blank")}
    >
      {/* 🖼️ Image */}
      <div className="h-40 w-full overflow-hidden">
        <img
          src={article.image || "https://via.placeholder.com/400x200"}
          alt={article.title}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
        />
      </div>

      {/* 📄 Content */}
      <div className="p-4 space-y-2">
        <h3 className="font-semibold text-sm line-clamp-2">
          {article.title}
        </h3>

        <p className="text-xs text-muted-foreground line-clamp-2">
          {article.description}
        </p>

        {/* 🔖 Bookmark */}
        <div className="flex justify-between items-center pt-2">
          <span className="text-xs text-primary">Read more →</span>

          <button
            onClick={(e) => {
              e.stopPropagation();
              onBookmark(article.id);
            }}
          >
            <Bookmark
              size={16}
              className={article.bookmarked ? "fill-primary text-primary" : ""}
            />
          </button>
        </div>
      </div>
    </div>
  );
};

export default NewsCard;