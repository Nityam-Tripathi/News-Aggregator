export interface NewsArticle {
  id: string;
  title: string;
  description: string;
  source: string;
  publishDate: string;
  url: string;
  imageUrl: string;
  category: string;
  bookmarked?: boolean;
}

export interface SourceReference {
  title: string;
  source: string;
  publishDate: string;
  url: string;
}

export const mockTrendingNews: NewsArticle[] = [
  {
    id: "1",
    title: "OpenAI Announces GPT-5 with Breakthrough Reasoning Capabilities",
    description: "The latest model shows unprecedented performance in complex reasoning tasks, scoring 95% on graduate-level benchmarks.",
    source: "TechCrunch",
    publishDate: "2026-04-05",
    url: "#",
    imageUrl: "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=400&h=250&fit=crop",
    category: "AI",
  },
  {
    id: "2",
    title: "SpaceX Starship Completes First Commercial Orbital Flight",
    description: "The fully reusable rocket system marks a new era in affordable space transportation.",
    source: "Reuters",
    publishDate: "2026-04-04",
    url: "#",
    imageUrl: "https://images.unsplash.com/photo-1516849841032-87cbac4d88f7?w=400&h=250&fit=crop",
    category: "Tech",
  },
  {
    id: "3",
    title: "Global Markets Rally as Inflation Drops to 2-Year Low",
    description: "Central banks signal potential rate cuts as consumer prices stabilize across major economies.",
    source: "Bloomberg",
    publishDate: "2026-04-04",
    url: "#",
    imageUrl: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=400&h=250&fit=crop",
    category: "Business",
  },
  {
    id: "4",
    title: "Premier League Title Race Intensifies with 3 Teams Level on Points",
    description: "Arsenal, Manchester City, and Liverpool enter the final stretch in the closest title race in decades.",
    source: "ESPN",
    publishDate: "2026-04-03",
    url: "#",
    imageUrl: "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=400&h=250&fit=crop",
    category: "Sports",
  },
  {
    id: "5",
    title: "Apple Vision Pro 2 Leaks Suggest Major Weight Reduction",
    description: "Sources indicate the next-gen headset will be 40% lighter with improved battery life.",
    source: "The Verge",
    publishDate: "2026-04-03",
    url: "#",
    imageUrl: "https://images.unsplash.com/photo-1592478411213-6153e4ebc07d?w=400&h=250&fit=crop",
    category: "Tech",
  },
  {
    id: "6",
    title: "EU Passes Landmark AI Regulation Framework",
    description: "New rules require transparency in AI systems and impose strict guidelines on high-risk applications.",
    source: "Financial Times",
    publishDate: "2026-04-02",
    url: "#",
    imageUrl: "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=400&h=250&fit=crop",
    category: "AI",
  },
];

export const mockAnswer = `## AI Industry Overview — April 2026

The AI landscape is undergoing rapid transformation with several key developments:

### Major Breakthroughs
- **GPT-5** has been announced with significant improvements in reasoning and multimodal capabilities
- **EU AI Act** implementation is reshaping how companies deploy AI systems across Europe
- Open-source models are closing the gap with proprietary solutions

### Market Impact
The global AI market is projected to reach **$500 billion** by end of 2026, driven by:
1. Enterprise adoption of generative AI tools
2. Increased investment in AI infrastructure
3. Growing demand for AI-powered automation

### Key Concerns
- Regulatory compliance costs are rising for AI companies
- Ethical AI deployment remains a challenge
- Workforce displacement concerns continue to drive policy discussions`;

export const mockSources: SourceReference[] = [
  { title: "OpenAI Announces GPT-5 with Breakthrough Reasoning", source: "TechCrunch", publishDate: "Apr 5, 2026", url: "#" },
  { title: "EU AI Act: What Companies Need to Know", source: "Financial Times", publishDate: "Apr 2, 2026", url: "#" },
  { title: "AI Market Projections for 2026-2030", source: "Bloomberg", publishDate: "Apr 1, 2026", url: "#" },
  { title: "The State of Open Source AI Models", source: "MIT Technology Review", publishDate: "Mar 30, 2026", url: "#" },
];

export const categories = [
  { name: "AI", icon: "Brain" },
  { name: "Tech", icon: "Cpu" },
  { name: "Sports", icon: "Trophy" },
  { name: "Business", icon: "TrendingUp" },
] as const;

export const recentSearches = [
  "Latest AI developments",
  "Stock market today",
  "SpaceX launch updates",
  "Premier League standings",
];
