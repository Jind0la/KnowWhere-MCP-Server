#!/usr/bin/env node
/**
 * KnowWhere CLI - Quick MCP Setup
 * 
 * Usage:
 *   npx @knowwhere/cli
 *   npx @knowwhere/cli --api-key YOUR_KEY
 */

import chalk from "chalk";
import inquirer from "inquirer";
import { homedir, platform } from "os";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";
import { dirname, join } from "path";

// =============================================================================
// Types
// =============================================================================

type MCPClient = "cursor" | "claude-desktop" | "claude-code" | "gemini-cli";

interface ClientConfig {
    id: MCPClient;
    name: string;
    configPath: {
        darwin: string;
        win32: string;
        linux: string;
    };
    configKey: string;
}

// =============================================================================
// Client Configurations
// =============================================================================

const CLIENTS: Record<MCPClient, ClientConfig> = {
    cursor: {
        id: "cursor",
        name: "Cursor IDE",
        configPath: {
            darwin: "~/.cursor/mcp.json",
            win32: "%APPDATA%\\Cursor\\mcp.json",
            linux: "~/.config/Cursor/mcp.json",
        },
        configKey: "mcpServers",
    },
    "claude-desktop": {
        id: "claude-desktop",
        name: "Claude Desktop",
        configPath: {
            darwin: "~/Library/Application Support/Claude/claude_desktop_config.json",
            win32: "%APPDATA%\\Claude\\claude_desktop_config.json",
            linux: "~/.config/Claude/claude_desktop_config.json",
        },
        configKey: "mcpServers",
    },
    "claude-code": {
        id: "claude-code",
        name: "Claude Code (CLI)",
        configPath: {
            darwin: "~/.claude/settings.json",
            win32: "%USERPROFILE%\\.claude\\settings.json",
            linux: "~/.claude/settings.json",
        },
        configKey: "mcpServers",
    },
    "gemini-cli": {
        id: "gemini-cli",
        name: "Gemini CLI",
        configPath: {
            darwin: "~/.config/gemini/settings.json",
            win32: "%APPDATA%\\gemini\\settings.json",
            linux: "~/.config/gemini/settings.json",
        },
        configKey: "mcpServers",
    },
};

const API_URL = "https://knowwhere-mcp-server-production.up.railway.app";

// =============================================================================
// Utility Functions
// =============================================================================

function expandPath(path: string): string {
    if (path.startsWith("~")) {
        return join(homedir(), path.slice(1));
    }
    if (path.includes("%APPDATA%")) {
        return path.replace("%APPDATA%", process.env.APPDATA || "");
    }
    if (path.includes("%USERPROFILE%")) {
        return path.replace("%USERPROFILE%", process.env.USERPROFILE || homedir());
    }
    return path;
}

function getPlatform(): "darwin" | "win32" | "linux" {
    const p = platform();
    if (p === "darwin" || p === "win32") return p;
    return "linux";
}

function getConfigPath(client: ClientConfig): string {
    const p = getPlatform();
    return expandPath(client.configPath[p]);
}

function readJsonFile(path: string): Record<string, unknown> {
    if (!existsSync(path)) {
        return {};
    }
    try {
        const content = readFileSync(path, "utf-8");
        return JSON.parse(content);
    } catch {
        return {};
    }
}

function writeJsonFile(path: string, data: Record<string, unknown>): void {
    const dir = dirname(path);
    if (!existsSync(dir)) {
        mkdirSync(dir, { recursive: true });
    }
    writeFileSync(path, JSON.stringify(data, null, 2), "utf-8");
}

function generateKnowWhereConfig(apiKey: string): Record<string, unknown> {
    return {
        url: `${API_URL}/sse`,
        headers: {
            Authorization: `Bearer ${apiKey}`,
        },
    };
}

// =============================================================================
// Main CLI
// =============================================================================

async function main() {
    console.log("\n");
    console.log(chalk.bold.cyan("  🧠 KnowWhere CLI Setup"));
    console.log(chalk.gray("  ─────────────────────────────────────"));
    console.log(chalk.gray("  Verbinde deinen AI-Client mit KnowWhere"));
    console.log("\n");

    // Parse CLI arguments
    const args = process.argv.slice(2);
    let apiKey: string | undefined;

    for (let i = 0; i < args.length; i++) {
        if (args[i] === "--api-key" && args[i + 1]) {
            apiKey = args[i + 1];
        }
    }

    // Step 1: Select client
    const { client } = await inquirer.prompt<{ client: MCPClient }>([
        {
            type: "list",
            name: "client",
            message: "Welchen AI-Client verwendest du?",
            choices: Object.values(CLIENTS).map((c) => ({
                name: c.name,
                value: c.id,
            })),
        },
    ]);

    const selectedClient = CLIENTS[client];
    const configPath = getConfigPath(selectedClient);

    console.log(chalk.gray(`\n  → Config-Datei: ${configPath}`));

    // Step 2: Get API key
    if (!apiKey) {
        const { inputKey } = await inquirer.prompt<{ inputKey: string }>([
            {
                type: "password",
                name: "inputKey",
                message: "Dein KnowWhere API Key:",
                mask: "*",
                validate: (input: string) =>
                    input.startsWith("kw_") || "API Key muss mit 'kw_' beginnen",
            },
        ]);
        apiKey = inputKey;
    }

    // Step 3: Read existing config
    const existingConfig = readJsonFile(configPath);
    const mcpServers = (existingConfig[selectedClient.configKey] || {}) as Record<
        string,
        unknown
    >;

    // Check if knowwhere already exists
    if ("knowwhere" in mcpServers) {
        const { overwrite } = await inquirer.prompt<{ overwrite: boolean }>([
            {
                type: "confirm",
                name: "overwrite",
                message: chalk.yellow(
                    "KnowWhere ist bereits konfiguriert. Überschreiben?"
                ),
                default: false,
            },
        ]);

        if (!overwrite) {
            console.log(chalk.gray("\n  Abgebrochen."));
            process.exit(0);
        }
    }

    // Step 4: Add KnowWhere config
    mcpServers["knowwhere"] = generateKnowWhereConfig(apiKey);
    existingConfig[selectedClient.configKey] = mcpServers;

    // Step 5: Write config
    try {
        writeJsonFile(configPath, existingConfig);
        console.log("\n");
        console.log(chalk.green("  ✅ KnowWhere erfolgreich konfiguriert!"));
        console.log("\n");
        console.log(chalk.gray("  Nächste Schritte:"));
        console.log(chalk.white(`  1. Starte ${selectedClient.name} neu`));
        console.log(
            chalk.white('  2. Sag deinem AI: "Merke dir, dass ich TypeScript mag"')
        );
        console.log(chalk.white('  3. Frag: "Was weisst du ueber mich?"'));
        console.log("\n");
        console.log(
            chalk.gray("  Dashboard: ") +
            chalk.cyan("https://knowwhere.dev/dashboard")
        );
        console.log("\n");
    } catch (error) {
        console.error(chalk.red("\n  ❌ Fehler beim Schreiben der Config:"));
        console.error(chalk.red(`     ${error}`));
        console.log("\n");
        console.log(chalk.yellow("  Manuelle Konfiguration:"));
        console.log(chalk.gray(`  Füge folgendes zu ${configPath} hinzu:`));
        console.log("\n");
        console.log(
            JSON.stringify({ knowwhere: generateKnowWhereConfig(apiKey) }, null, 2)
        );
        console.log("\n");
        process.exit(1);
    }
}

main().catch((error) => {
    console.error(chalk.red("Fehler:"), error.message);
    process.exit(1);
});
