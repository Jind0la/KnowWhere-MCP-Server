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
    configPaths: {
        darwin: string[];
        win32: string[];
        linux: string[];
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
        configPaths: {
            darwin: ["~/.cursor/mcp.json"],
            win32: ["%APPDATA%\\Cursor\\mcp.json"],
            linux: ["~/.config/Cursor/mcp.json"],
        },
        configKey: "mcpServers",
    },
    "claude-desktop": {
        id: "claude-desktop",
        name: "Claude Desktop",
        configPaths: {
            darwin: ["~/Library/Application Support/Claude/claude_desktop_config.json"],
            win32: ["%APPDATA%\\Claude\\claude_desktop_config.json"],
            linux: ["~/.config/Claude/claude_desktop_config.json"],
        },
        configKey: "mcpServers",
    },
    "claude-code": {
        id: "claude-code",
        name: "Claude Code (CLI)",
        configPaths: {
            darwin: ["~/.claude/settings.json", "~/.config/claude/settings.json"],
            win32: ["%USERPROFILE%\\.claude\\settings.json", "%APPDATA%\\claude\\settings.json"],
            linux: ["~/.claude/settings.json", "~/.config/claude/settings.json"],
        },
        configKey: "mcpServers",
    },
    "gemini-cli": {
        id: "gemini-cli",
        name: "Gemini CLI",
        configPaths: {
            darwin: [
                "~/.gemini/settings.json",
                "~/.config/gemini/settings.json",
                "~/.config/gemini/config.json"
            ],
            win32: [
                "%APPDATA%\\gemini\\settings.json",
                "%USERPROFILE%\\.gemini\\settings.json"
            ],
            linux: [
                "~/.gemini/settings.json",
                "~/.config/gemini/settings.json",
                "~/.config/gemini/config.json"
            ],
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
    const platformStr = getPlatform();
    const candidatePaths = selectedClient.configPaths[platformStr].map(expandPath);

    // Find existing config files
    const existingFilePaths = candidatePaths.filter(p => existsSync(p));

    let configPath: string;

    if (existingFilePaths.length === 0) {
        // Use the first one as default if none exist
        configPath = candidatePaths[0];
    } else if (existingFilePaths.length === 1) {
        // Use the only one that exists
        configPath = existingFilePaths[0];
    } else {
        // Ask the user which one to use if multiple exist
        console.log(chalk.yellow(`\n  ⚠️  Mehrere Konfigurationsdateien für ${selectedClient.name} gefunden.`));
        const { choice } = await inquirer.prompt<{ choice: string }>([
            {
                type: "list",
                name: "choice",
                message: "Welche Datei soll aktualisiert werden?",
                choices: existingFilePaths.map(p => ({
                    name: p.replace(homedir(), "~"),
                    value: p
                }))
            }
        ]);
        configPath = choice;
    }

    console.log(chalk.gray(`\n  → Config-Datei: ${configPath.replace(homedir(), "~")}`));

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
