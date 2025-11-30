# CellByte Chat

A conversational AI chatbot that enables natural language interaction with CSV data using RAG (Retrieval-Augmented Generation) and specialized LLM tools.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                             │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         PARENT AGENT (LangGraph)                        │
│                                                                         │
│  Orchestrates all tools, maintains conversation state, routes queries   │
└─────────────────────────────────────────────────────────────────────────┘
          │                    │                    │                │
          ▼                    ▼                    ▼                ▼
    ┌──────────┐        ┌──────────┐        ┌──────────┐      ┌──────────┐
    │ RAG Tool │        │ Plotter  │        │Analytics │      │Web Search│
    │          │        │   Tool   │        │   Tool   │      │   Tool   │
    └──────────┘        └──────────┘        └──────────┘      └──────────┘
```

---

## Core Framework

- **LangChain**: Foundation for LLM interactions and tool management
- **LangGraph**: Agent orchestration and state management

---

## RAG Framework

### CSV Ingestion Pipeline

Each CSV file is processed by a **non-agentic LLM** to generate:

1. **Vectorstore**: Embeddings for semantic search over CSV content
2. **Metadata**: Structured context about the file (columns, data types, summary statistics, etc.)

> **Design Choice**: Using a dedicated non-agentic LLM to parase the doc and generate a metadata, that can be used to give the main one more context about the data it fetches. Main question is: How to give LLM a single VecStore with all csv and the context separated? Maybe I pass context through an additional system promtp when the chat is initiated.

### RAG Tool Architecture

- The parent agent has access to RAG as a tool
- Each RAG tool instance is scoped to a specific CSV file
- Tool includes file metadata for context-aware retrieval
- Enables the agent to "know what it knows" about available data

---

## Non-RAG Agentic Tools

### 1. Plotter Utility

**Purpose**: Generate visualizations from CSV data

**Flow**:
```
Parent Agent
    │
    ├─► [Plot Prompt + Data]
    │
    ▼
Plot LLM (Non-Agentic)
    │
    ├─► Generates Plotly code / HTML
    │
    ▼
Parent Agent
    │
    ├─► Returns HTML visualization
    │
    ▼
User Interface
```

**Capabilities**:
- Bar charts, line graphs, scatter plots, histograms
- Heatmaps, box plots, pie charts
- Custom visualizations based on natural language requests

**Output Format**: HTML (Plotly.js) for interactive, embeddable charts

---

### 2. Analytics Tool

**Purpose**: Perform statistical analysis on CSV data

**Flow**:
```
Parent Agent
    │
    ├─► [Analytics Prompt + Data]
    │
    ▼
Analytics LLM (Non-Agentic)
    │
    ├─► Generates Python code (SciPy/NumPy/Pandas)
    │
    ▼
Code Execution Environment
    │
    ├─► Returns computed results
    │
    ▼
Parent Agent
    │
    ├─► Interprets and formats results
    │
    ▼
User Interface
```

**Key Assumption**: 
> ⚠️ **LLMs DO NOT perform numerical calculations directly.** All computations are delegated to proper numerical libraries (SciPy, NumPy, Pandas). The LLM's role is purely code generation.

**Capabilities**:
- Descriptive statistics (mean, median, std, etc.)
- Correlation analysis
- Hypothesis testing
- Regression analysis
- Distribution fitting

---

### 3. Web Search Tool

**Purpose**: Augment responses with external knowledge

**Use Cases**:
- Looking up domain-specific terminology
- Finding context for data interpretation
- Answering questions that extend beyond the CSV content

---

## Key Design Assumptions

### LLM Role Separation

| Component | Type | Responsibility |
|-----------|------|----------------|
| Parent Agent | Agentic (LangGraph) | Orchestration, routing, conversation |
| CSV Ingestion | Non-Agentic | Vectorstore + metadata generation |
| Plot LLM | Non-Agentic | Visualization code generation |
| Analytics LLM | Non-Agentic | Statistical code generation |

### Why Non-Agentic Sub-LLMs?

1. **Predictability**: No recursive tool calls or unexpected behaviors
2. **Performance**: Lower latency without agent loop overhead
3. **Focused Output**: Single-purpose prompts yield better results
4. **Cost Efficiency**: Simpler chains = fewer tokens

### Data Flow Principles

1. **Data stays structured**: CSVs are passed as structured data, not raw text
2. **Code over calculation**: LLMs generate executable code, not numerical results
3. **HTML as visualization format**: Universal, embeddable, interactive

---

## Unclear Requirements / Open Questions

### Document Transformation Feature

**Question**: What does "transforming outputs" mean in this context?

Two possible interpretations:

#### Option A: Output Transformation (Post-LLM)
Converting LLM-generated outputs to different formats without re-parsing the original CSV.

```
LLM Response (Markdown/HTML Report)
    │
    ▼
Transformation Layer
    │
    ├─► PDF → DOCX
    ├─► Markdown → PDF
    ├─► Translation (EN → ES, etc.)
    │
    ▼
User receives transformed output
```

**Use case**: User asks for a report, then requests "give me that as a Word doc" or "translate to Spanish"

#### Option B: Input Parsing (Pre-LLM)
Converting non-CSV documents INTO parsable structures so the LLM can analyze them.

```
Non-CSV Document (PDF, DOCX, Images)
    │
    ▼
Marker / Document Parser
    │
    ├─► Extracts text, tables, structure
    ├─► Converts to CSV / structured format
    │
    ▼
Now analyzable by the main pipeline
```

**Use case**: User uploads a PDF report with tables → system extracts data → LLM can now query it

---

### Two Document Categories

| Category | Description | Processing |
|----------|-------------|------------|
| **CSV Docs** | Primary data sources | Direct vectorstore + metadata pipeline |
| **Non-CSV Docs** | PDFs, DOCX, images with tables | Marker → structured extraction → then standard pipeline |

**Potential Tool**: [Marker](https://github.com/VikParuchuri/marker) for document parsing

**Open Questions**:
- Do we support both A and B?
- Should non-CSV docs be first-class citizens or just "converted to CSV"?
- How to handle mixed documents (PDF with both text narrative AND data tables)?
- Translation: LLM-based or dedicated translation API?

---

## Tech Stack (Planned)

- **Framework**: LangChain + LangGraph
- **Embeddings**: GPTs Large model
- **Vector Store**: FAISS
- **Visualization**: Plotly
- **Analytics**: Pandas, NumPy, SciPy (more to be thought off)
- **Web Search**: DuckDuckGo's existing tools should be ok.

---

## Project Status

🚧 **In Development**


