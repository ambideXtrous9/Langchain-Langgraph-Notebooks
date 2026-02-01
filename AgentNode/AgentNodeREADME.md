# LangGraph E-Commerce Agent

A production-ready, agentic AI application built with **LangGraph**, **LangChain**, and **FastAPI**. This agent acts as an e-commerce assistant capable of searching for products, checking real-time inventory, and performing web searches for reviews and comparisons.

## 🚀 Features

*   **Advanced Agentic Workflow**: Uses `LangGraph` to manage state and complex tool interactions.
*   **Multi-Tool Strategy**: Enforced logic requiring multiple data sources before answering:
    1.  `product_search`: Internal catalog search.
    2.  `get_inventory`: Real-time stock checking.
    3.  `duckduckgo_search`: External web search for reviews/context.
*   **Robust Middleware**:
    *   **PII Redaction**: Automatically scrubs sensitive emails from inputs/outputs.
    *   **Summarization**: Auto-condenses long conversation histories to manage context window.
    *   **Rate Limiting**: Custom middleware to prevent abuse and track error counts.
*   **Streaming API**: proper **FastAPI** integration supporting NDJSON streaming for real-time frontend experiences.
*   **Containerized**: Full **Docker** and **Docker Compose** support for easy deployment.

## 📂 Project Structure

```text
.
├── src/
│   ├── agent.py           # Core agent definition & graph construction
│   ├── config.py          # Configuration, Prompts, & LLM setup
│   ├── middleware.py      # Custom middleware (PII, Rate Limit, etc.)
│   ├── models.py          # Pydantic data models (State, Response Schemas)
│   ├── server.py          # FastAPI application & streaming logic
│   └── tools.py           # Tool definitions
├── main.py                # CLI entry point for testing
├── Dockerfile             # Multi-stage Docker build
├── docker-compose.yml     # Container orchestration
└── requirements.txt       # Project dependencies
```

## 🛠️ Installation & Setup

### Prerequisites
*   Python 3.12+
*   Docker & Docker Compose (optional)
*   OpenAI API Key

### Local Setup

1.  **Clone the repository**:
    ```bash
    git clone <repo-url>
    cd langgraph-create-agent
    ```

2.  **Create and activate a virtual environment**:
    *This project is configured to auto-activate the `.langgraph` venv if you use `direnv` or the provided `.bashrc` snippet.*
    ```bash
    python3.12 -m venv .langgraph
    source .langgraph/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration**:
    Create a `.env` file in the root directory and add your OpenAI API key:
    ```env
    OPENAI_API_KEY=your_openai_api_key_here
    ```

## 🏃‍♂️ Usage

### 1. CLI Mode (Testing)
Run the agent interactively in the terminal to verify logic.
```bash
python main.py
```

### 2. API Server (Production)
Start the FastAPI server with streaming support.
```bash
uvicorn src.server:app --host 0.0.0.0 --port 8025 --reload
```

**Test the Stream**:
```bash
curl -N -X POST "http://localhost:8025/stream" \
     -H "Content-Type: application/json" \
     -d '{"query": "Are there gaming laptops under $1500?", "customer_id": "test_user"}'
```

## 🐳 Docker Deployment

Build and run the entire application stack using Docker Compose. The services will automatically load environment variables from your `.env` file.

```bash
docker compose up --build
```
The API will be available at `http://localhost:8025`.

### 3. API Documentation (Swagger UI)
FastAPI provides automatic interactive documentation. Once the server is running, visit:
*   **Swagger UI**: `http://localhost:8025/docs`
*   **ReDoc**: `http://localhost:8025/redoc`

### 4. API Endpoints

#### POST `/stream`
Streams the agent's execution steps in real-time.

**Request Body**:
```json
{
  "query": "string",
  "customer_id": "string (optional)",
  "context": "string (optional)"
}
```

**Example Payload**:
```json
{
    "customer_id" : "user_456",
    "query" : "Are there any affordable gaming laptops under $1500 currently in stock?",
    "context" : "VIP customer, prefers gaming laptops"
}
```

**Response**:
Returns an NDJSON (Newline Delimited JSON) stream. Each line corresponds to a step in the agent's execution.
```json
{"type": "AIMessage", "content": "...", "tool_calls": [...]}
{"type": "ToolMessage", "content": "..."}
{"type": "AIMessage", "content": "...", "structured_response": {...}}
```

#### GET `/health`
Health check endpoint.
**Response**: `{"status": "ok"}`


## 🧠 Architecture Details

### The "Three-Tool" Rule
The agent is explicitly instructed (via System Prompt in `src/config.py`) to **never** answer a user query without first maximizing information gathering. It essentially pre-fetches:
1.  **Internal Data**: Product details.
2.  **Logistics Data**: Stock levels.
3.  **External Data**: Reviews and market comparisons.

### Structured Output
The agent guarantees a JSON response matching the schema defined in `src/models.py`:
```json
{
  "intent": "query|purchase|support",
  "action": "respond|tool|escalate",
  "confidence": 0.9,
  "rationale": "Explanation of the decision..."
}
```

## 📝 License
[MIT](LICENSE)
