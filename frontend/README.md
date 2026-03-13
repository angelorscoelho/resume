# Siemens Energy — AI Maintenance Assistant Frontend

A lightweight single-page chat interface for the Gas Turbine AI Maintenance Assistant.

## Features

- Clean Siemens-branded chat UI
- **Markdown rendering** via [marked.js](https://marked.js.org/) — bold, headings, lists, tables, code blocks all render properly
- Source citation display with relevance scores
- Keyboard shortcut: **Enter** to send, **Shift+Enter** for new line

## Usage

### Local development

Open `index.html` directly in a browser **and** configure the API URL:

```js
// In frontend/index.html, update API_URL to your local SAM endpoint:
const API_URL = 'http://localhost:3000';
```

Start the SAM local API (set required environment variables first):

```bash
cd ../backend
sam local start-api \
  --parameter-overrides \
    GeminiApiKey=<your-key> \
    S3BucketName=<your-bucket>
```

Then open `frontend/index.html` in your browser.

### Production

Deploy this folder to [Vercel](https://vercel.com/) (zero config — `vercel.json` is already included).

Set the `SIEMENS_API_URL` runtime variable on the Vercel project to your deployed AWS API Gateway URL:

```
https://<api-id>.execute-api.<region>.amazonaws.com
```

Then, in `index.html`, update the `API_URL` line:

```js
const API_URL = 'https://<api-id>.execute-api.<region>.amazonaws.com';
```

Or inject it at deploy time by replacing the constant in your CI pipeline.
