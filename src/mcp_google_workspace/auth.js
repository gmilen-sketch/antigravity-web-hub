const { google } = require('googleapis');
const readline = require('readline');
const fs = require('fs');
const path = require('path');

// Client credentials loaded from environment or fallback placeholder
const CLIENT_ID = process.env.GOOGLE_WORKSPACE_CLIENT_ID || '982618493963-placeholder.apps.googleusercontent.com';
const CLIENT_SECRET = process.env.GOOGLE_WORKSPACE_CLIENT_SECRET || 'GOCSPX-placeholder';
const REDIRECT_URI = process.env.GOOGLE_WORKSPACE_REDIRECT_URI || 'https://vertexaisearch.cloud.google.com/static/oauth/oauth.html';

const SCOPES = [
  'https://www.googleapis.com/auth/drive',
  'https://www.googleapis.com/auth/spreadsheets',
  'https://www.googleapis.com/auth/gmail.modify',
  'https://www.googleapis.com/auth/calendar',
  'https://www.googleapis.com/auth/documents',
  'https://www.googleapis.com/auth/bigquery'
];

const TOKEN_PATH = path.join(__dirname, 'tokens.json');

const oauth2Client = new google.auth.OAuth2(
  CLIENT_ID,
  CLIENT_SECRET,
  REDIRECT_URI
);

function getAuthUrl() {
  return oauth2Client.generateAuthUrl({
    access_type: 'offline',
    prompt: 'consent',
    scope: SCOPES,
  });
}

async function exchangeCodeForTokens(code) {
  try {
    const { tokens } = await oauth2Client.getToken(code);
    fs.writeFileSync(TOKEN_PATH, JSON.stringify(tokens, null, 2));
    console.log('\nSuccess! Tokens acquired and saved to tokens.json.');
    console.log('Token scopes granted:', tokens.scope);
    if (tokens.refresh_token) {
      console.log('Refresh token received and saved.');
    } else {
      console.warn('WARNING: No refresh token received. You may need to revoke access first if you already authorized this app.');
    }
  } catch (error) {
    console.error('Error exchanging code for tokens:', error.message);
  }
}

function main() {
  if (fs.existsSync(TOKEN_PATH)) {
    console.log(`Token file already exists at ${TOKEN_PATH}`);
    const existingTokens = JSON.parse(fs.readFileSync(TOKEN_PATH, 'utf8'));
    console.log('Scopes in existing token:', existingTokens.scope);
    console.log('If you wish to re-authenticate, delete tokens.json and run this script again.');
    process.exit(0);
  }

  const authUrl = getAuthUrl();
  console.log('========================================================================');
  console.log('GOOGLE WORKSPACE MCP SERVER OAUTH SETUP');
  console.log('========================================================================\n');
  console.log('1. Open the following URL in your browser to authorize the application:');
  console.log(`\n${authUrl}\n`);
  console.log('2. After authorizing, you will be redirected to a page showing an authorization code.');
  console.log('   (Or copy the "code" parameter from the URL bar of the redirected page)');
  console.log('3. Paste the authorization code below:\n');

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  rl.question('Enter authorization code: ', async (code) => {
    rl.close();
    const cleanCode = decodeURIComponent(code.trim());
    console.log(`Exchanging code: "${cleanCode.substring(0, 10)}..."`);
    await exchangeCodeForTokens(cleanCode);
  });
}

if (require.main === module) {
  main();
}
