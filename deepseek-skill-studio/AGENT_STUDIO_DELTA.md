# Agent Studio Delta v1.2

This version adds a full local Agent Studio experience on top of Ollama DeepSeek.

## Added

- Agent Mode, Chat Mode, and Skill Mode selector.
- Installed Ollama models dropdown powered by `GET /models`.
- On-demand agent creation from a natural-language prompt using `POST /agent/create`.
- Dynamic agent persistence in `backend/agents/agents.json`.
- Chat window using selected agent behavior and optional uploaded/GitHub context.
- `/chat` backend endpoint with chat history support.
- Reusable context panel for GitHub repo URL, branch, include/exclude paths, and uploaded files.
- Existing DOCX/PPTX/Markdown generation remains available in Agent Mode and Skill Mode.

## How to use

1. Start Ollama and pull one or more models.
2. Start the app using the one-click script.
3. Pick a model from the dropdown.
4. Use Create Agent on Demand to define a new agent, for example:
   - Create an agent that reviews codebase patent alignment and produces a technical presentation.
   - Create an audit evidence agent that reads uploaded files and creates SOX-ready exception reports.
5. Choose Agent Mode to generate a file, or Chat Mode to interact conversationally with the selected agent.
