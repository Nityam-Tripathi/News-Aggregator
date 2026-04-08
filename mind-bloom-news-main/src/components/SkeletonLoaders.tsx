export const AnswerSkeleton = () => (
  <div className="w-full max-w-3xl mx-auto bg-card border border-border rounded-2xl p-6 space-y-4">
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-xl shimmer" />
      <div className="space-y-2">
        <div className="w-16 h-3 rounded shimmer" />
        <div className="w-48 h-4 rounded shimmer" />
      </div>
    </div>
    <div className="space-y-3 pt-2">
      <div className="w-full h-3 rounded shimmer" />
      <div className="w-5/6 h-3 rounded shimmer" />
      <div className="w-4/6 h-3 rounded shimmer" />
      <div className="w-full h-3 rounded shimmer" />
      <div className="w-3/4 h-3 rounded shimmer" />
    </div>
  </div>
);

export const NewsCardSkeleton = () => (
  <div className="bg-card border border-border rounded-2xl overflow-hidden">
    <div className="aspect-[16/9] shimmer" />
    <div className="p-5 space-y-3">
      <div className="w-full h-4 rounded shimmer" />
      <div className="w-3/4 h-4 rounded shimmer" />
      <div className="w-full h-3 rounded shimmer" />
      <div className="w-1/2 h-3 rounded shimmer" />
    </div>
  </div>
);

export const SourceSkeleton = () => (
  <div className="flex items-start gap-3 p-4 bg-card border border-border rounded-xl">
    <div className="w-9 h-9 rounded-lg shimmer shrink-0" />
    <div className="flex-1 space-y-2">
      <div className="w-full h-3.5 rounded shimmer" />
      <div className="w-2/3 h-3 rounded shimmer" />
    </div>
  </div>
);
