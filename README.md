# CellByte Chat

A conversational AI chatbot that enables natural language interaction with CSV data using RAG (Retrieval-Augmented Generation) and specialized LLM tools.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                             │
│                            (Next.js Frontend)                           │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         PARENT AGENT (LangGraph)                        │
│                                                                         │
│  Orchestrates all tools, maintains conversation state, routes queries   │
└─────────────────────────────────────────────────────────────────────────┘
          │                    │                    │                
          ▼                    ▼                    ▼                
    ┌──────────┐        ┌──────────┐        ┌──────────┐      ┌──────────┐
    │ RAG Tool │        │ Plotter  │        │Analytics │      │~~Web~~   │
    │ (Search) │        │   Tool   │        │   Tool   │      │~~Search~~│
    └──────────┘        └──────────┘        └──────────┘      └──────────┘
         ✅                  ✅                  ✅               🚫 TODO
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- OpenAI API Key

### Option 1: Run Locally (Development)

```bash
# Clone the repository
git clone <repo-url>
cd cellbyte_chat

# Create .env file
echo "OPENAI_API_KEY=your-key-here" > .env

# Backend setup
pip install -r requirements.txt
cd backend
uvicorn api:app --reload --port 8000

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

Access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 2: Run with Docker (Production)

```bash
# Clone and setup
git clone <repo-url>
cd cellbyte_chat

# Create .env file
echo "OPENAI_API_KEY=your-key-here" > .env

# Build and run
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

Access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

Data persists in Docker volumes:
- `cellbyte_database` - FAISS index and file metadata
- `cellbyte_history` - Chat history
- `cellbyte_logs` - Application logs

---

## Assumptions

### LLM Role Separation

| Component | Type | Responsibility |
|-----------|------|----------------|
| Parent Agent | Agentic (LangGraph) | Orchestration, routing, conversation |
| CSV Ingestion | Non-Agentic | Vectorstore + metadata generation |
| Plot LLM | Non-Agentic | Visualization code generation |
| Analytics LLM | Non-Agentic | Statistical code generation |

### Design Principles

1. **LLMs don't calculate** - All numerical computations are delegated to Python libraries (Pandas, NumPy, SciPy). LLMs only generate code.

2. **Non-agentic sub-LLMs** - Plotter and Analytics tools use single-shot LLM calls (not agents) for:
   - Predictability: No recursive tool calls
   - Performance: Lower latency
   - Cost efficiency: Fewer tokens
   - Flexibility with models: Claude would make more sense here -- replace OpenAI's endpoint with requesty and use multiple models for minimal changes to the codebase.

3. **Retry with feedback** - When generated code fails, the error is fed back to the LLM to fix (up to 3 attempts). Happens a lot, because of missing metadata in some cases (especially plotting ones)

4. **Data stays structured** - CSVs are passed as DataFrames, not raw text. However, if it's a multi-table Excel, this might struggle with finding the header and index.

5. **HTML for visualizations** - Plotly charts are returned as embeddable HTML. Give users some interactivity with the plots (much better than matplotlib). 

---

## Features

### 1. CSV Ingestion & RAG Search

Upload CSV/TSV/Excel files. The system automatically:
- Generates LLM-powered descriptions
- Creates FAISS vector embeddings
- Extracts metadata (columns, types, statistics)

### 2. Visualization (Plotter Tool)

Ask for charts in natural language:
- "Give me a distribution of additional benefit ratings as a pie chart"
- "Show me the range of yearly therapy costs by additional benefit rating in a plot"

![Plotting Example](readme_images/plotting.png)

### 3. Analytics (Analyze Tool)

Ask for statistics and calculations:
- "What are the average yearly therapy costs in Non-small cell lung cancer?"
- "Are there any products that received a higher benefit rating in a reassessment in the same disease area."

![Analytics Example](readme_images/analytics.png)

---

## Shortcomings with the current version

- Completely AI-coded frontend, only the APIs are vetted for sanity.
- The metadata logic **DOES NOT** scale well with more documents, as it increases the system prompt by a lot. Need an HNSW-like solution here, so that the metadata of only the top layer can be fed to the model.
- ```create_react_agent``` was done for speed, but it is suboptimal in terms of flexibility. A custom execution graph with an execution handler would be much better for the main application, because of more control over the tool call flow (API's could be made to stream for example).
- The system prompt can be improved a lot to improve the behaviour of the agent, especially in the tool calling order and importance.
- Cannot handle non-homogeneous spreadsheets with multiple tables.
- Analytics do not work if data from more than 1 file is required -- but this is fairly easy to pull off.
- All OpenAI chatbots used here. There is a provision for specialized ones in the LLM utils, but I lack the API keys or access to something like requesty.
- The database is local -- need to sync with S3 with a persistent container volume.

---

## Potential Improvements

### Short-term

- [ ] Add web search tool for external knowledge augmentation
- [ ] Remove ```create_react_agent``` and convert this to a streaming API so that the user does not have to sit around for the code to return something.
- [ ] System Prompt for agent for tool calls flow needs a lot of fixing: For example, calling the rag search before creating a plot/analytics prompt
- [ ] Analysis that joins multiple files together. Nothing defines joins, so cross doc queries are hard to answer except by completely relying on files. Simple fix, however, with a Pydantic base class that takes a list of files for the tool calls.

### Long-term

- [ ] **Important One**: Scaling with documents, as in the case of 100 documents, 100 metadatas in the system prompts will be overburdening.
- [ ] Related to the previous, document clustering. Basically, sort of a higher-level metadata that describes available columns and overviews in a collection of similar documents: It massively helps the AI understand where to look, from past experiences.
- [ ] Support for unstructured CSV/Documents: this would not work if the spreadsheet has multiple non-homogeneous tables, or rather, even multiple headers. Plus, the datatype handling currently is not the best.
- [ ] Grafana and OpenTelemetry with loggers for deployment.

---

## Unclear Requirements / Open Questions

### Document Transformation

Coming from the requirement: "transforming outputs (e.g., converting PDF → DOCX or translating a report) without re‑parsing the original CSV,", which I did not fully understand

**Question**: Should the system support document format conversion?

| Option | Description | Example |
|--------|-------------|---------|
| **Output transformation** | Convert LLM outputs to different formats | "Export this as PDF" |
| **Input parsing** | Parse non-CSV docs into analyzable structure | Upload PDF with tables → extract to CSV |

### OR Multi-Document Analysis

- Should users be able to JOIN data across multiple CSVs?
- How to handle conflicting column names?
- What's the UX for specifying relationships?

### Non-CSV Documents

| Category | Current Support | Future? |
|----------|-----------------|---------|
| CSV/TSV | ✅ Full support | - |
| Excel (.xlsx, .xls) | ✅ Full support | - |
| PDF with tables | ❌ | Marker integration |
| Word documents | ❌ | Marker integration |
| Images with tables | ❌ |  Marker with OCR |

## Tool Flows

### RAG Search Tool Flow

```
User Query: "Find drugs with major additional benefit"
    │
    ▼
┌─────────────────────────────┐
│       Parent Agent          │
│  (Decides to use RAG tool)  │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│      FAISS Vector Store     │
│   Semantic similarity search │
└─────────────────────────────┘
    │
    ▼
Returns top-k matching rows
    │
    ▼
Agent summarizes findings for user
```

### Plotter Tool Flow

```
User Query: "Create a pie chart of benefit distribution"
    │
    ▼
┌─────────────────────────────┐
│       Parent Agent          │
│ (Decides to use Plot tool)  │
└─────────────────────────────┘
    │
    ├─► [Plot Request + Dataset Context]
    │
    ▼
┌─────────────────────────────┐
│   Plot LLM (Non-Agentic)    │
│   Generates Plotly code     │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│   Code Execution (exec)     │
│   Runs generated Python     │
└─────────────────────────────┘
    │
    ├─► Success? Return HTML
    │
    ├─► Error? Feed back to LLM (retry up to 3x)
    │
    ▼
┌─────────────────────────────┐
│      User Interface         │
│  Renders interactive chart  │
└─────────────────────────────┘
```

### Analytics Tool Flow

```
User Query: "What is the median yearly therapy cost?"
    │
    ▼
┌─────────────────────────────┐
│       Parent Agent          │
│(Decides to use Analyze tool)│
└─────────────────────────────┘
    │
    ├─► [Analytics Request + Dataset Context]
    │
    ▼
┌─────────────────────────────┐
│ Analytics LLM (Non-Agentic) │
│ Generates pandas/scipy code │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│   Code Execution (exec)     │
│   Available: pd, np, scipy, │
│   sklearn, re               │
└─────────────────────────────┘
    │
    ├─► Success? Return results dict
    │
    ├─► Error? Feed back to LLM (retry up to 3x)
    │
    ▼
┌─────────────────────────────┐
│       Parent Agent          │
│  Formats results for user   │
└─────────────────────────────┘
```


---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Agent Framework** | LangChain + LangGraph |
| **LLM** | OpenAI GPT-4o / GPT-5.1 |
| **Embeddings** | OpenAI text-embedding-3-large |
| **Vector Store** | FAISS |
| **Backend** | FastAPI + Uvicorn |
| **Frontend** | Next.js 14 + React |
| **Visualization** | Plotly |
| **Analytics** | Pandas, NumPy, SciPy, scikit-learn |
| **Containerization** | Docker + Docker Compose |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/healthz` | Health check |
| `POST` | `/files/ingest` | Upload and ingest a CSV file |
| `GET` | `/files` | List all ingested files |
| `DELETE` | `/files/{filename}` | Delete a file |
| `POST` | `/chat` | Send message to agent |
| `POST` | `/chat/refresh` | Refresh agent metadata |
| `GET` | `/history` | List all chat sessions |
| `GET` | `/history/{id}` | Get specific chat history |
| `PUT` | `/history/{id}` | Update chat history |
| `DELETE` | `/history/{id}` | Delete chat history |


---

## Project Structure

```
cellbyte_chat/
├── backend/
│   ├── api.py                    # FastAPI endpoints
│   └── src/
│       ├── agent.py              # LangGraph agent
│       ├── general_utils/        # Shared utilities
│       │   ├── logger.py
│       │   └── file_utils.py
│       └── llm_utils/            # LLM-specific code
│           ├── csv_ingestion.py  # File ingestion & FAISS
│           ├── plotting_utils.py # Chart generation
│           ├── analytics_utils.py# Statistical analysis
│           └── tools.py          # Agent tools
├── frontend/
│   ├── app/                      # Next.js pages
│   ├── components/               # React components
│   └── lib/                      # API client & types
├── database/                     # FAISS index & metadata
├── history/                      # Chat history JSON files
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

