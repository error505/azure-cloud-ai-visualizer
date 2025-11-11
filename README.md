# Cloud Visualizer Pro
![alt text](image.png)
Cloud Visualizer Pro is an open-source web application for visually designing Azure architecture diagrams, generating grounded Infrastructure-as-Code (IaC) (Bicep and Terraform), and orchestrating deployments. It combines a React/TypeScript frontend with a FastAPI backend and integrates the Microsoft Agent Framework (MAF) and Model Context Protocol (MCP) to ground LLM-driven IaC generation in official documentation.
![alt text](image-5.png)
![alt text](image-4.png)

## High-level Architecture

- Frontend: React + TypeScript (Vite) — located in `src/`
  - Uses modern UI primitives and a palette of Azure service icons.
  - Key components: diagram canvas, service palette, inspector panel, top bar, deploy modal.
- Backend: FastAPI (Python) — located in `backend/app/`
  - Provides REST API endpoints for project storage, IaC generation, MCP integration, and deployments.
  - Uses Pydantic Settings for configuration and integrates Azure storage clients optionally.
- Agent & MCP integration:
  - Microsoft Agent Framework (agent-framework, agent-framework-azure-ai) is used to run LLM-driven agents.
  - The app integrates external MCP servers (Microsoft Learn MCP and HashiCorp Terraform MCP) using a streamable MCP transport to ground model outputs in live documentation and provider schemas.

## Key Features
![alt text](image-2.png)
- Visual diagram editor for Azure architectures.
- Grounded IaC generation:
  - Bicep generation with optional MCP grounding via Microsoft Learn MCP.
  - Terraform generation with optional HashiCorp Terraform MCP grounding.
- IaC validation using MCP-backed schema checks.
- Deploy orchestration pipeline (hooks for Azure SDK clients).
- Offline/CI-friendly fallbacks: MockAgent/OpenAI fallback paths when MCP/MAF are unavailable.
![alt text](image-6.png)

## Quickstart (Development)

Prerequisites
- Node.js (for frontend / Vite)
- Python 3.12+ and a virtual environment
- Optional: Azure credentials if you plan to test deployments

1) Frontend: install and run

```powershell
cd frontend
# install dependencies (uses pnpm, npm or yarn depending on your setup)
pnpm install
pnpm run dev
```

2) Backend: install dependencies using uv

```powershell
cd backend
uv install
```

3) Set up environment (for easy development without Azure setup):

```powershell
# Copy example environment file
cp .env.example .env
# Edit .env and set:
# USE_OPENAI_FALLBACK=true
# OPENAI_API_KEY=your_openai_key_here
```

4) Run backend (development)

```powershell
# from backend directory
uv run uvicorn main:app --reload --port 8000
```

4) Open the frontend (Vite dev server) and it should proxy to the backend (see CORS settings in `backend/.env`).

## Using docker to run project locally
A `docker-compose.yml` file is provided to run both frontend and backend using Docker.

Poulate a `.env` file in the `backend/` directory as described above (with OpenAI fallback or MCP settings).

1) Build and run containers:

```powershell
docker-compose up --build
```
2) Access the frontend at `http://localhost:3000` (or the port specified in the `docker-compose.yml`).


## Configuration

Configuration uses a `.env` file at `backend/.env` loaded by Pydantic Settings.
Important environment keys:

- OPENAI_API_KEY / USE_OPENAI_FALLBACK — enable OpenAI fallback for development
- AZURE_OPENAI_KEY / AZURE_AI_PROJECT_ENDPOINT — configure Azure AI Project / MAF
- AZURE_MCP_BICEP_URL — Microsoft Learn MCP base endpoint (recommended: `https://learn.microsoft.com/api/mcp`)
- TERRAFORM_MCP_URL — HashiCorp Terraform MCP endpoint (if available)
- AZURE_MCP_BICEP_FORCE / TERRAFORM_MCP_FORCE — set to `true` to force initializing MCP tools (useful in dev/test)

Notes about MCP
- The MCP endpoints require a streamable HTTP transport (SSE/chunked) and are intended to be used only from compliant MCP clients (for example `MCPStreamableHTTPTool` from `agent-framework`). Manual browser access will often return `405 Method Not Allowed`.
- Microsoft Learn MCP (`https://learn.microsoft.com/api/mcp`) exposes tools such as `microsoft_docs_search`, `microsoft_code_sample_search` and `microsoft_docs_fetch`. Use these via MCP tools passed to the agent.
- HashiCorp's MCP endpoint may apply rate-limits or access constraints (you may receive `429 Too Many Requests`). If you need a stable Terraform MCP integration consider contacting HashiCorp or using a local/proxied MCP registry.

## How MCP is used in this project
- The backend creates a streamable MCP tool singleton (`app.deps.get_mcp_bicep_tool` and `get_mcp_terraform_tool`) which opens a long-lived MCP session to the configured server.
- The agent passes that tool into `chat_agent.run(prompt, tools=mcp_tool)` so the LLM can invoke tool calls and sample documentation content during generation.
- The code contains safe fallbacks: if MCP initialization fails, the system logs the reasons and falls back to AI-only generation (or MockAgent for tests).

## Development notes and troubleshooting

- If you see an ImportError related to `prepare_function_call_results`, update/install `agent-framework` and `agent-framework-azure-ai` to compatible versions. The project includes a small compatibility shim to help in mixed-version dev environments.
- If MCP initialization fails with `Session terminated` or stalls, verify:
  - `AZURE_MCP_BICEP_URL` is the base MCP endpoint (e.g. `https://learn.microsoft.com/api/mcp`)
  - Your network/proxy doesn't block chunked streaming HTTP or SSE
  - HashiCorp MCP may return `429` when rate-limited; try again later or request access

## Testing

- Backend unit/integration tests are located under `backend/` and use pytest/pytest-asyncio.
- There is a small test harness `backend/test_terraform_mcp.py` that exercises the Terraform generator and demonstrates MockAgent fallback behavior when MCP is unavailable.

## Security & Secrets

- Never commit secrets (API keys, connection strings) to the repository. Put secrets in `backend/.env` (not checked in) or in a secure secret manager.
- When deploying, use managed identities or secure vaults instead of environment variables for production credentials.


## Roadmap & Contributions

- Contributions: Please open a pull request against `main`. Small, focused PRs with tests or screenshots are preferred.
- Tasks / Issues: Use the project's issue tracker for bugs, feature requests, or development tasks. Label and link PRs to issue numbers where applicable.
- Code of Conduct: Be respectful and follow standard open-source community practices.

## License

- This project is released under the MIT License. See the `LICENSE` file for details.


## Contact / Maintainers

If you have questions or need help reproducing issues, open an issue describing the problem and include logs from the backend (set `LOG_LEVEL=DEBUG` in `.env` to get detailed MCP handshake logs).