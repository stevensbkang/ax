# AX demo for Portainer

Assets for the Portainer × AX intent-based launch prototype. This repo is
public: never commit keys or tokens.

| Path | What it is |
| --- | --- |
| `catalog/` | The GitOps catalog: AX Workspaces and Portainer agent profiles |
| `billing-demo/` | A small project with a failing test for the agent to fix |
| `agent/` | The demo coding agent, built on AX's default task runner |
| `gateway/` | The model gateway: the only component that holds the provider key |

## Flow

1. A user describes a task in Portainer, e.g. "fix the failing billing tests".
2. Portainer's planner picks a Workspace and an agent profile the user may use.
3. Portainer expands the profile into an AX Task and validates it like any manifest.
4. The agent runs in a gVisor sandbox, calls the model through the gateway, and
   writes its result to `/workspace/.ax-result.json`.

## Running the demo project's tests

```bash
cd billing-demo && python3 -m unittest discover -s tests -v
```
