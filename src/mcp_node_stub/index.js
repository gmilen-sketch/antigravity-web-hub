#!/usr/bin/env node
const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { CallToolRequestSchema, ListToolsRequestSchema } = require("@modelcontextprotocol/sdk/types.js");

const server = new Server(
  {
    name: "deep-research-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "deep_research",
        description: "Performs deep research on a given topic.",
        inputSchema: {
          type: "object",
          properties: {
            topic: { type: "string", description: "The topic to research" },
          },
          required: ["topic"],
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "deep_research") {
    const topic = request.params.arguments.topic;
    return {
      content: [
        {
          type: "text",
          text: `Initiating deep research for topic: ${topic}. Please visit https://ai.google.dev/gemini-api/docs/deep-research for more details.`,
        },
      ],
    };
  }
  throw new Error("Tool not found");
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}
main().catch((err) => {
  console.error(err);
  process.exit(1);
});
