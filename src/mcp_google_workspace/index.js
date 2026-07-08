#!/usr/bin/env node
const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { CallToolRequestSchema, ListToolsRequestSchema } = require("@modelcontextprotocol/sdk/types.js");
const { google } = require('googleapis');
const fs = require('fs');
const path = require('path');
const os = require('os');

const TOKEN_PATH = path.join(__dirname, 'tokens.json');
const ADC_PATH = path.join(os.homedir(), '.config/gcloud/application_default_credentials.json');

// Initialize MCP Server
const server = new Server(
  {
    name: "google-workspace-mcp",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Helper to get authenticated Google Auth client
function getAuthClient() {
  if (fs.existsSync(TOKEN_PATH)) {
    console.error('Using custom tokens.json for Google Workspace auth.');
    const tokens = JSON.parse(fs.readFileSync(TOKEN_PATH, 'utf8'));
    const client_id = process.env.GOOGLE_WORKSPACE_CLIENT_ID || '982618493963-placeholder.apps.googleusercontent.com';
    const client_secret = process.env.GOOGLE_WORKSPACE_CLIENT_SECRET || 'GOCSPX-placeholder';
    const redirect_uri = process.env.GOOGLE_WORKSPACE_REDIRECT_URI || 'https://vertexaisearch.cloud.google.com/static/oauth/oauth.html';
    const oauth2Client = new google.auth.OAuth2(
      client_id,
      client_secret,
      redirect_uri
    );
    oauth2Client.setCredentials(tokens);
    return oauth2Client;
  } else if (fs.existsSync(ADC_PATH)) {
    console.error('tokens.json not found. Falling back to active GCE Application Default Credentials (ADC).');
    const adc = JSON.parse(fs.readFileSync(ADC_PATH, 'utf8'));
    const oauth2Client = new google.auth.OAuth2(
      adc.client_id,
      adc.client_secret,
      'urn:ietf:wg:oauth:2.0:oob'
    );
    oauth2Client.setCredentials({
      refresh_token: adc.refresh_token
    });
    return oauth2Client;
  } else {
    throw new Error('No credentials available. Run oauth setup first or login via gcloud application-default.');
  }
}

// Helper to generate base64url raw email
function makeEmail(to, subject, body) {
  const str = [
    `To: ${to}`,
    'Content-Type: text/html; charset=utf-8',
    'MIME-Version: 1.0',
    `Subject: ${subject}`,
    '',
    body,
  ].join('\r\n');
  return Buffer.from(str)
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

// 1. List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "gmail_list_messages",
        description: "List recent messages from the user's Gmail inbox.",
        inputSchema: {
          type: "object",
          properties: {
            maxResults: { type: "number", description: "Maximum number of messages to return (default 10)" },
            q: { type: "string", description: "Search query to filter messages (standard Gmail search syntax)" },
          },
        },
      },
      {
        name: "gmail_send_email",
        description: "Send an email message to a recipient.",
        inputSchema: {
          type: "object",
          properties: {
            to: { type: "string", description: "Recipient's email address" },
            subject: { type: "string", description: "Email subject line" },
            body: { type: "string", description: "Email body content (HTML or plain text)" },
          },
          required: ["to", "subject", "body"],
        },
      },
      {
        name: "calendar_list_events",
        description: "List upcoming events from the user's primary Google Calendar.",
        inputSchema: {
          type: "object",
          properties: {
            maxResults: { type: "number", description: "Maximum number of events to return (default 10)" },
          },
        },
      },
      {
        name: "calendar_create_event",
        description: "Create a new event in the user's primary Google Calendar.",
        inputSchema: {
          type: "object",
          properties: {
            summary: { type: "string", description: "Title of the calendar event" },
            startTime: { type: "string", description: "Event start time in ISO-8601 format (e.g. 2026-07-03T10:00:00Z)" },
            endTime: { type: "string", description: "Event end time in ISO-8601 format (e.g. 2026-07-03T11:00:00Z)" },
            description: { type: "string", description: "Optional description or notes for the event" },
          },
          required: ["summary", "startTime", "endTime"],
        },
      },
      {
        name: "drive_list_files",
        description: "List files stored in the user's Google Drive.",
        inputSchema: {
          type: "object",
          properties: {
            pageSize: { type: "number", description: "Maximum number of files to return (default 10)" },
          },
        },
      },
      {
        name: "sheets_create_spreadsheet",
        description: "Create a new Google Spreadsheet.",
        inputSchema: {
          type: "object",
          properties: {
            title: { type: "string", description: "Title of the new spreadsheet" },
          },
          required: ["title"],
        },
      },
    ],
  };
});

// 2. Call tools
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const auth = getAuthClient();

  try {
    switch (name) {
      case "gmail_list_messages": {
        const gmail = google.gmail({ version: 'v1', auth });
        const res = await gmail.users.messages.list({
          userId: 'me',
          maxResults: args.maxResults || 10,
          q: args.q || undefined,
        });

        const messages = res.data.messages || [];
        const details = await Promise.all(
          messages.map(async (msg) => {
            const m = await gmail.users.messages.get({ userId: 'me', id: msg.id, format: 'minimal' });
            return { id: msg.id, snippet: m.data.snippet };
          })
        );

        return {
          content: [{ type: "text", text: JSON.stringify(details, null, 2) }],
        };
      }

      case "gmail_send_email": {
        const gmail = google.gmail({ version: 'v1', auth });
        const raw = makeEmail(args.to, args.subject, args.body);
        const res = await gmail.users.messages.send({
          userId: 'me',
          requestBody: { raw },
        });

        return {
          content: [{ type: "text", text: `Email sent successfully. Message ID: ${res.data.id}` }],
        };
      }

      case "calendar_list_events": {
        const calendar = google.calendar({ version: 'v3', auth });
        const res = await calendar.events.list({
          calendarId: 'primary',
          timeMin: new Date().toISOString(),
          maxResults: args.maxResults || 10,
          singleEvents: true,
          orderBy: 'startTime',
        });

        const events = res.data.items || [];
        const result = events.map(e => ({
          summary: e.summary,
          start: e.start.dateTime || e.start.date,
          end: e.end.dateTime || e.end.date,
          link: e.htmlLink
        }));

        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "calendar_create_event": {
        const calendar = google.calendar({ version: 'v3', auth });
        const res = await calendar.events.insert({
          calendarId: 'primary',
          requestBody: {
            summary: args.summary,
            description: args.description || "",
            start: { dateTime: args.startTime, timeZone: "UTC" },
            end: { dateTime: args.endTime, timeZone: "UTC" },
          },
        });

        return {
          content: [{ type: "text", text: `Event created successfully. Event Link: ${res.data.htmlLink}` }],
        };
      }

      case "drive_list_files": {
        const drive = google.drive({ version: 'v3', auth });
        const res = await drive.files.list({
          pageSize: args.pageSize || 10,
          fields: 'nextPageToken, files(id, name, mimeType)',
        });

        return {
          content: [{ type: "text", text: JSON.stringify(res.data.files || [], null, 2) }],
        };
      }

      case "sheets_create_spreadsheet": {
        const sheets = google.sheets({ version: 'v4', auth });
        const res = await sheets.spreadsheets.create({
          requestBody: {
            properties: { title: args.title },
          },
        });

        return {
          content: [{ type: "text", text: `Spreadsheet created successfully. URL: ${res.data.spreadsheetUrl}` }],
        };
      }

      default:
        throw new Error(`Tool not found: ${name}`);
    }
  } catch (error) {
    console.error(`Error executing tool ${name}:`, error);
    return {
      isError: true,
      content: [{ type: "text", text: `API Error: ${error.message}` }],
    };
  }
});

// Run server using Stdio transport
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Google Workspace MCP Server successfully running on stdio transport.");
}

main().catch((err) => {
  console.error("Fatal error running MCP Server:", err);
  process.exit(1);
});
