# 🏃 RunLifestyle Agent

A stateful, AI-powered running lifestyle assistant built with the Google Agent Development Kit (ADK), Google Agent Platform, and Gemini models. **RunLifestyle** helps runners discover routes, calculate pace and calorie metrics, check outdoor running weather, locate nearby parks, and generate custom visual route artwork and video teasers.

![RunLifestyle Demo](./demo.gif)

---

## ✨ Features & Capabilities

The agent implements the following features and integrations in `app/agent.py`:

- **🧠 Cross-Session Long-Term Memory**:
  Integrated with **Vertex AI Memory Bank** (`PreloadMemoryTool` and `generate_memories_callback`). Automatically persists user preferences, fitness goals, and health/allergy constraints across sessions.

- **🗄️ Firestore Running Route Database**:
  - `search_running_routes`: Query running routes stored in Google Cloud Firestore by location or terrain type (e.g. paved, trail).
  - `add_running_route`: Store new user-submitted running routes with distance, difficulty, rating, and description into Firestore.

- **☀️ Real-Time Running Weather & Advice**:
  - `get_live_running_weather`: Fetches live outdoor weather conditions (temperature, wind speed) and tailored running safety advice via Open-Meteo API.

- **📍 Geocoding & Nearby Places**:
  - `geocode_address`: Converts unstructured address strings into geographic coordinates `(latitude, longitude)`.
  - `find_nearby_places`: Discovers nearby parks, gyms, and running tracks via Google Places API.

- **⏱️ Pace & Calorie Burn Calculator**:
  - `calculate_pace_and_calories`: Calculates average running pace (`min/mile` or `min/km`) and estimates calorie burn based on runner weight and distance.

- **🎨 Route Artwork Generation**:
  - `generate_route_image`: Generates route illustrations using `gemini-3.1-flash-lite-image` in the `global` region. Saves local artifacts (`tool_context.save_artifact`) and uploads image bytes directly to a public Google Cloud Storage bucket.

- **🎬 Short Route Video Teasers**:
  - `generate_route_video`: Generates short video clips using Google's `gemini-omni-flash-preview` in the `global` region. Saves local artifacts and uploads raw video bytes to Google Cloud Storage.

- **💻 Code Sandbox Execution**:
  - Executes Python code safely in the cloud via `AgentEngineSandboxCodeExecutor`.

- **🎨 Rich A2UI Interface Cards**:
  - Uses `A2uiSchemaManager` (v0.8) and `a2ui_callback` to return structured UI cards (Card, Column, Row, Text, Image) instead of plain text.

---

## 🛠️ Architecture & Project Structure

```
runlifestyle/
├── app/
│   ├── agent.py          # Main ADK agent logic, system prompt, and tools
│   └── a2ui_utils.py     # A2UI callback handler for rich card rendering
├── frontend/
│   ├── main.py           # FastAPI proxy translating browser requests to A2A
│   ├── requirements.txt  # Frontend dependencies
│   └── static/
│       └── index.html    # Custom web chat interface with example chips
├── agents-cli-manifest.yaml  # Agent Platform deployment manifest
├── deployment_metadata.json  # Remote deployment resource trackers
├── pyproject.toml        # ADK project dependencies
└── demo.gif              # Animated demonstration preview
```

---

## 🚀 Setup & Local Execution

### 1. Prerequisites

- Python 3.11+
- `uv` package manager (`pip install uv`)
- Google Cloud SDK (`gcloud`) authenticated with access to Vertex AI, Firestore, and Cloud Storage.

### 2. Install Dependencies

```bash
uv sync
pip install -r frontend/requirements.txt
```

### 3. Run Agent Playground Locally

Start the local ADK Web playground with attached Vertex AI Memory Bank:

```bash
uv run adk web . --port 8080 --reload_agents --memory_service_uri=agentengine://<MEMORY_BANK_ID>
```

### 4. Run Custom Chat Frontend Proxy Locally

To start the FastAPI chat frontend proxy locally:

```bash
cd frontend
export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_ID>/locations/<REGION>/reasoningEngines/<ENGINE_ID>"
export AGENT_DIRECTORY="app"
python main.py
```

Open a web browser and navigate to the server port output by Uvicorn to interact with the RunLifestyle chat interface.

---

## ☁️ Deployment Commands

Deploy the agent to Agent Platform using `agents-cli`:

```bash
agents-cli deploy --project <PROJECT_ID> --no-confirm-project --update-env-vars GOOGLE_MAPS_API_KEY=<API_KEY>
```

Deploy the chat frontend to Cloud Run:

```bash
cd frontend
gcloud run deploy runlifestyle-frontend \
  --source . \
  --region us-east1 \
  --project <PROJECT_ID> \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME="<RESOURCE_NAME>",AGENT_DIRECTORY="app" \
  --allow-unauthenticated
```
