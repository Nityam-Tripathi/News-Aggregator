# 🧠 InsightStream

An AI-powered news aggregation and question-answering system built on a full **Retrieval-Augmented Generation (RAG)** pipeline. Ask any question about current events and get grounded, cited answers backed by real-time news articles.

**Live Demo → [InsightStream](https://news-aggregator-ten-sandy.vercel.app/)**

---

## What It Does

You type a question like *"What is happening in AI this week?"* and the system:

1. Fetches real-time news articles related to your query
2. Generates vector embeddings for semantic understanding
3. Searches the database for the most relevant articles using cosine similarity
4. Sends retrieved context to an LLM to generate a grounded answer
5. Returns the answer with clickable sources, images, and timestamps

No hallucination. No generic responses. Every answer is backed by real, recent news.

---

## Architecture

```
User Query
    ↓
Dynamic News Fetch (NewsAPI)
    ↓
Embedding Generation (SentenceTransformers)
    ↓
Vector Storage (PostgreSQL + pgvector)
    ↓
Cosine Similarity Search
    ↓
Context Assembly (top 5 deduplicated articles)
    ↓
LLM Answer Generation (Groq / LLaMA 3)
    ↓
Answer + Sources + Images → React UI
```

---

## Features

- **Automated ingestion agent** — APScheduler fetches and processes news every 30 minutes with no manual intervention
- **Semantic search** — cosine similarity over 384-dimensional embeddings using pgvector
- **Dynamic per-query fetching** — fresh articles fetched for every user query before searching the DB
- **Deduplication** — MD5 hashing prevents duplicate articles across ingestion cycles
- **Timestamp-aware ranking** — results ordered by both relevance and recency
- **Trending topics** — high-frequency keywords from the last 24 hours, clickable to trigger a search
- **Source attribution** — every answer includes article titles, images, links, and publish times
- **Analytics dashboard** — total article count and top keyword frequency visualization

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI |
| Database | PostgreSQL |
| Vector Storage | pgvector extension |
| Embeddings | SentenceTransformers (all-MiniLM-L6-v2) |
| LLM | Groq API (LLaMA 3 8B) |
| Scheduler | APScheduler |
| Frontend | React + Tailwind CSS |
| Containerization | Docker + Docker Compose |
| Deployment | Render (backend) + Vercel (frontend) |

---

## Project Structure

```
project/
│
├── GenAI/                        # Backend
│   ├── app/
│   │   ├── main.py               # FastAPI app + all endpoints
│   │   ├── database.py           # SQLAlchemy connection
│   │   ├── models.py             # NewsArticle model with pgvector
│   │   ├── news_fetcher.py       # NewsAPI ingestion + hashing
│   │   ├── embeddings.py         # SentenceTransformer embedding
│   │   ├── rag_pipeline.py       # Groq LLM answer generation
│   │   └── scheduler.py          # APScheduler background job
│   ├── requirements.txt
│   └── .env.example
│
├── mind-bloom-news-main/         # Frontend
│   ├── src/
│   │   ├── pages/
│   │   │   └── Index.tsx         # Main UI page
│   │   └── components/
│   │       ├── SearchBar.tsx
│   │       ├── AnswerSection.tsx
│   │       ├── SourceCard.tsx
│   │       ├── NewsCard.tsx
│   │       └── SkeletonLoaders.tsx
│   ├── package.json
│   └── .env.example
│
└── docker-compose.yml            # PostgreSQL + pgvector container
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker Desktop

### 1. Clone the repository

```bash
git clone https://github.com/your-username/ai-news-assistant.git
cd ai-news-assistant
```

### 2. Start PostgreSQL with pgvector

```bash
docker-compose up -d
```

Connect and enable the extension:

```bash
docker exec -it news_db psql -U postgres -d newsdb
```

```sql
CREATE EXTENSION vector;
\q
```

### 3. Setup the backend

```bash
cd GenAI
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

Create your `.env` file:

```env
NEWS_API_KEY=your_newsapi_key
GROQ_API_KEY=your_groq_key
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/newsdb
```

Create database tables:

```bash
python create_tables.py
```

Start the backend:

```bash
uvicorn app.main:app --reload
```

API docs available at: `http://127.0.0.1:8000/docs`

### 4. Setup the frontend

```bash
cd mind-bloom-news-main
npm install
```

Create your `.env` file:

```env
VITE_API_URL=http://127.0.0.1:8000
```

Start the frontend:

```bash
npm run dev
```

Open: `http://localhost:5173`

### 5. Ingest your first articles

With the backend running, call the ingest endpoint:

```
POST http://127.0.0.1:8000/ingest
```

Or open `http://127.0.0.1:8000/docs` and run it from the Swagger UI.

After ingestion, the scheduler will automatically fetch new articles every 30 minutes.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| POST | `/ingest` | Manually trigger news ingestion |
| GET | `/ask?query=` | RAG question answering |
| GET | `/search?query=` | Semantic search only |
| GET | `/top-news` | Latest 10 articles |
| GET | `/trending` | Trending topics (last 24h) |
| GET | `/analytics` | All articles for analytics |

---

## Environment Variables

### Backend (`GenAI/.env`)

| Variable | Description |
|---|---|
| `NEWS_API_KEY` | API key from [newsapi.org](https://newsapi.org) |
| `GROQ_API_KEY` | API key from [console.groq.com](https://console.groq.com) |
| `DATABASE_URL` | PostgreSQL connection string |

### Frontend (`mind-bloom-news-main/.env`)

| Variable | Description |
|---|---|
| `VITE_API_URL` | Backend URL (local or deployed) |

---

## Deployment

### Backend → Render

1. Go to [render.com](https://render.com) → New Web Service
2. Connect your GitHub repo
3. Set **Root Directory** to `GenAI`
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port 10000`
6. Add environment variables in the Render dashboard
7. Create a PostgreSQL instance on Render and copy the internal URL into `DATABASE_URL`

### Frontend → Vercel

1. Go to [vercel.com](https://vercel.com) → Import Project
2. Connect your GitHub repo
3. Set **Root Directory** to `mind-bloom-news-main`
4. Add environment variable: `VITE_API_URL` = your Render backend URL
5. Deploy

---

## How RAG Works in This Project

Traditional search returns documents that contain your keywords. RAG goes further:

**Retrieve** — the user's query is converted to an embedding vector. pgvector finds the top articles with the closest cosine distance.

**Augment** — retrieved articles are assembled into a structured context prompt with titles and content.

**Generate** — the LLM receives only the retrieved context and generates an answer strictly grounded in those articles.

The result is an answer that is factually tied to real, recent sources — not the LLM's training data.

---

## Future Improvements

- Redis caching for faster repeated queries
- Hybrid search combining keyword + vector retrieval (BM25 + cosine)
- User authentication and personalized news feeds
- Sentiment analysis pipeline on ingested articles
- Fine-tuned embedding model for the news domain

---

Built by **Nityam Tripathi**
