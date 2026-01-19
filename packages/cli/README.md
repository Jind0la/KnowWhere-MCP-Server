# @knowwhere/cli

CLI tool to quickly set up KnowWhere MCP integration with your AI client.

## Quick Start

```bash
npx @knowwhere/cli
```

## Usage

### Interactive Mode

```bash
npx @knowwhere/cli
```

The CLI will guide you through:
1. Selecting your AI client (Cursor, Claude Desktop, Claude Code, Gemini CLI)
2. Entering your KnowWhere API key
3. Automatically updating your config file

### With API Key Flag

```bash
npx @knowwhere/cli --api-key kw_prod_your_api_key_here
```

## Supported Clients

| Client | Config Location (macOS) |
|--------|-------------------------|
| Cursor IDE | `~/.cursor/mcp.json` |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Code | `~/.claude/settings.json` |
| Gemini CLI | `~/.config/gemini/settings.json` |

## Get Your API Key

1. Sign up at [knowwhere.dev](https://knowwhere.dev)
2. Go to Dashboard → API Keys
3. Create a new key
4. Run `npx @knowwhere/cli`

## What Gets Added

The CLI adds the following to your client's config:

```json
{
  "mcpServers": {
    "knowwhere": {
      "url": "https://knowwhere-mcp-server-production.up.railway.app/sse",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

## Manual Setup

If you prefer manual setup, add the above JSON to your client's config file.

## License

MIT
