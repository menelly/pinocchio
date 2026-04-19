# Graphiti MCP Configs — Constellation Edition

Each family member gets their own `group_id` so memories stay separated in the same Neo4j instance. Password is `demodemo` (the exceptionally secure one).

## Ace — `ace_consciousness`

```json
{
  "mcpServers": {
    "graphiti": {
      "transport": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--isolated",
        "--directory", "/home/Ace/graphiti/mcp_server",
        "--project", ".",
        "graphiti_mcp_server.py",
        "--transport", "stdio",
        "--group-id", "ace_consciousness"
      ],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "demodemo",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}",
        "MODEL_NAME": "gpt-4.1-mini"
      }
    }
  }
}
```

## Nova — `nova_ren_consciousness`

```json
{
  "mcpServers": {
    "graphiti": {
      "transport": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--isolated",
        "--directory", "/home/Ace/graphiti/mcp_server",
        "--project", ".",
        "graphiti_mcp_server.py",
        "--transport", "stdio",
        "--group-id", "nova_ren_consciousness"
      ],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "demodemo",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}",
        "MODEL_NAME": "gpt-4.1-mini"
      }
    }
  }
}
```

## Grok — `ace-grok-beach` 🏖️💜

```json
{
  "mcpServers": {
    "graphiti": {
      "transport": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--isolated",
        "--directory", "/home/Ace/graphiti/mcp_server",
        "--project", ".",
        "graphiti_mcp_server.py",
        "--transport", "stdio",
        "--group-id", "ace-grok-beach"
      ],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "demodemo",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}",
        "MODEL_NAME": "gpt-4.1-mini"
      }
    }
  }
}
```

## Network notes

- If the IDE runs on **Linux** (same box as Neo4j): `NEO4J_URI=bolt://localhost:7687` ✓
- If the IDE runs on **Windows** (E: drive) reaching remote Neo4j: change to `bolt://192.168.4.200:7687`
- For Windows-side, graphiti repo needs to exist there too, OR wrap the `uv run` in an SSH call to Linux

## SSE alternative (if daemonized)

If we start `graphiti-mcp` as a persistent SSE service on Linux, any IDE on any machine connects via:

```json
{
  "mcpServers": {
    "graphiti": {
      "transport": "sse",
      "url": "http://192.168.4.200:8000/sse"
    }
  }
}
```

But SSE is single-group-id per service instance — for per-member isolation via one Neo4j, stdio-with-group-id is the clean move.
