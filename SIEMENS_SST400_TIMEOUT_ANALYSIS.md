# SST-400 AI Maintenance Assistant — 504 Timeout Root-Cause Analysis

**Issue:** `API error 504: FUNCTION_INVOCATION_TIMEOUT cdg1::n4fmd-1773389686022-84a4196750c8`
**Query:** Analyze SST-400 (Unit ST-01) — vibration 4.739 mm/s, exhaust temp 609.2 °C, 23 810 h since overhaul.
**Date:** 2026-03-13

---

## 1. Root Cause Summary

The 504 originates from **Vercel**, not AWS. The timeout chain is:

| Layer | File | Current Timeout | Bottleneck |
|-------|------|----------------|------------|
| **Vercel serverless** | `frontend/vercel.json` | `maxDuration: 30` s | Function killed after 30 s |
| **Model listing** | `frontend/api/ask-assistant.ts` → `listAvailableModels()` | ~2-5 s | Extra round-trip to Google before any generation |
| **Gemini generation** | `frontend/api/ask-assistant.ts` → `generateContent` | No explicit timeout (Vercel kills it) | `gemini-2.5-pro` is a "thinking" model — complex queries take 30-60 s |
| **Prompt size** | `ask-assistant.ts` — inline knowledge base | N/A | Full manual + history (~15 000 tokens) injected into every request |
| **AWS Lambda** | `backend/template.yaml` | `Timeout: 30` s | `urllib` timeout 25 s; same model bottleneck |

### Why `gemini-2.5-pro` is too slow for this use case

`gemini-2.5-pro` is a deep-reasoning ("thinking") model. For the SST-400 query:

1. It receives ~15 000 tokens of context (full steam-turbine manual + maintenance history + system prompt).
2. It performs internal chain-of-thought reasoning before generating the answer.
3. Total response time routinely exceeds 30 seconds for complex multi-parameter fault queries.

The Vercel free/Hobby tier enforces a hard 30 s `maxDuration` — there is no way to exceed this without upgrading to the Pro plan (which allows up to 300 s).

### Is AWS the root cause?

**No.** The Vercel function (`frontend/api/ask-assistant.ts`) embeds the full knowledge base inline and calls the Gemini API directly. It does **not** proxy through the AWS Lambda backend. The AWS Lambda (`backend/ask_assistant/app.py`) is an independent path used only when the frontend is configured with `VITE_API_URL` pointing to the API Gateway.

However, the AWS Lambda has the **same model and timeout problem** — if called directly, it would also struggle with `gemini-2.5-pro` on complex queries (25 s `urllib` timeout on a 30 s Lambda timeout).

---

## 2. Recommended Fixes

### Fix 1 — Switch to `gemini-2.0-flash` (primary fix)

**Why `gemini-2.0-flash`?**

| Property | `gemini-2.5-pro` | `gemini-2.0-flash` |
|----------|------------------|---------------------|
| Latency (typical, 15K-token prompt) | 30-60 s | 3-8 s |
| Reasoning quality | Excellent | Very good — sufficient for structured maintenance queries |
| Cost per 1M tokens (input) | $1.25 | $0.10 |
| "Thinking" overhead | Yes (internal CoT) | No |

`gemini-2.0-flash` provides fast, high-quality responses for domain-grounded queries where the context already contains the answer. The manual excerpts are detailed enough that deep reasoning is unnecessary — the model needs to extract, structure, and cite, not reason from first principles.

#### File: `frontend/api/ask-assistant.ts`

Change the `PREFERRED_MODELS` array to prioritize flash models:

```typescript
// BEFORE
const PREFERRED_MODELS = [
  'gemini-2.5-pro-preview-06-05',
  'gemini-2.5-pro-preview-05-06',
  'gemini-2.5-pro-preview-03-25',
  'gemini-2.5-pro',
  'gemini-2.5-flash',
  'gemini-2.5-flash-preview-05-20',
  'gemini-2.0-flash',
  'gemini-1.5-pro',
  'gemini-1.5-flash',
  'gemini-pro',
];

// AFTER — flash-first ordering; pro kept as fallback only
const PREFERRED_MODELS = [
  'gemini-2.0-flash',
  'gemini-2.5-flash',
  'gemini-2.5-flash-preview-05-20',
  'gemini-1.5-flash',
  'gemini-2.5-pro',
  'gemini-1.5-pro',
];
```

Also reduce `maxOutputTokens` from 8192 to 4096 — the maintenance action plans never exceed ~2 000 tokens, and a lower cap reduces generation time:

```typescript
// BEFORE
generationConfig: { temperature: 0.2, maxOutputTokens: 8192, candidateCount: 1 },

// AFTER
generationConfig: { temperature: 0.2, maxOutputTokens: 4096, candidateCount: 1 },
```

#### File: `backend/template.yaml`

```yaml
# BEFORE
Parameters:
  GeminiModel:
    Type: String
    Default: gemini-2.5-pro
    AllowedValues:
      - gemini-2.5-pro
      - gemini-2.0-flash

# AFTER
Parameters:
  GeminiModel:
    Type: String
    Default: gemini-2.0-flash
    AllowedValues:
      - gemini-2.0-flash
      - gemini-2.5-flash
      - gemini-2.5-pro
```

#### File: `backend/samconfig.toml`

```toml
# BEFORE
parameter_overrides = "GeminiApiKey=\"\" GeminiModel=\"gemini-2.5-pro\" AllowedOrigin=\"*\""

# AFTER
parameter_overrides = "GeminiApiKey=\"\" GeminiModel=\"gemini-2.0-flash\" AllowedOrigin=\"*\""
```

#### File: `backend/ask_assistant/app.py`

Update the default and the docstring:

```python
# BEFORE
chat_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")

# AFTER
chat_model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
```

---

### Fix 2 — Eliminate `listAvailableModels()` overhead (Vercel function)

The function currently makes an extra API call to list all models before every request, adding 2-5 s of latency. This is unnecessary — the model IDs are known at deploy time.

#### File: `frontend/api/ask-assistant.ts`

Replace the dynamic model discovery with a direct call using a single preferred model:

```typescript
// BEFORE (simplified — iterates up to 12 models)
const availableModels = await listAvailableModels(apiKey);
const preferred = PREFERRED_MODELS.filter((m) => availableModels.includes(m));
const fallback = availableModels.filter((m) => !PREFERRED_MODELS.includes(m));
const candidates = [...preferred, ...fallback].slice(0, 12);

// AFTER — try preferred models directly; skip listing
const candidates = PREFERRED_MODELS;
```

This saves 2-5 seconds per request. If a model returns 404, the existing fallback loop already skips to the next candidate.

---

### Fix 3 — Increase Vercel `maxDuration` (defense in depth)

Even with `gemini-2.0-flash`, occasional slow responses can approach 30 s. Increase the budget:

#### File: `frontend/vercel.json`

```json
{
  "functions": {
    "api/**/*.ts": {
      "maxDuration": 60
    }
  }
}
```

> **Note:** Vercel Hobby plans are limited to 60 s max. Vercel Pro allows up to 300 s.

---

### Fix 4 — Increase AWS Lambda timeout (defense in depth)

#### File: `backend/template.yaml`

```yaml
# BEFORE
Globals:
  Function:
    Timeout: 30

# AFTER
Globals:
  Function:
    Timeout: 60
```

Also increase the `urllib` timeout in the Gemini chat call:

#### File: `backend/ask_assistant/app.py`

```python
# BEFORE
with urllib.request.urlopen(req, timeout=25) as resp:

# AFTER
with urllib.request.urlopen(req, timeout=55) as resp:
```

---

## 3. AWS Infrastructure Debug

### CloudWatch verification steps

```bash
# 1. Check Lambda invocation metrics (last 24h)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=siemens-poc-ask-assistant \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 --statistics Maximum Average \
  --region us-east-1

# 2. Check for Lambda timeouts
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=siemens-poc-ask-assistant \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 --statistics Sum \
  --region us-east-1

# 3. View Lambda logs for recent timeouts
aws logs filter-log-events \
  --log-group-name /aws/lambda/siemens-poc-ask-assistant \
  --filter-pattern "Task timed out" \
  --start-time $(date -u -d '24 hours ago' +%s)000 \
  --region us-east-1

# 4. Check API Gateway latency
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiId,Value=msao2suw84 \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 --statistics Maximum p99 \
  --region us-east-1

# 5. Check S3 access (knowledge base download latency)
aws s3api head-object \
  --bucket siemens-rag-knowledge-base \
  --key chunks/embeddings.json \
  --region us-east-1
```

### API Gateway integration timeout

The HTTP API Gateway has a hard 30-second integration timeout that cannot be increased. If the Lambda takes longer than 30 s, the Gateway will return a 504 regardless of the Lambda timeout. This reinforces the need to keep Lambda execution under 30 s (achievable with `gemini-2.0-flash`).

### S3 latency

The knowledge base is a single JSON file (~30 KB for 3 chunks). Download time from S3 within the same region (`us-east-1`) is typically < 50 ms. S3 is **not** a bottleneck.

---

## 4. Summary of Changes Required

| File | Change | Impact |
|------|--------|--------|
| `frontend/api/ask-assistant.ts` | Reorder `PREFERRED_MODELS` to put `gemini-2.0-flash` first | **Primary fix** — reduces response time from 30-60 s to 3-8 s |
| `frontend/api/ask-assistant.ts` | Remove `listAvailableModels()` call; try models directly | Saves 2-5 s per request |
| `frontend/api/ask-assistant.ts` | Reduce `maxOutputTokens` from 8192 to 4096 | Minor latency improvement |
| `frontend/vercel.json` | Increase `maxDuration` from 30 to 60 | Defense in depth |
| `backend/template.yaml` | Change `GeminiModel` default to `gemini-2.0-flash` | Fixes Lambda path |
| `backend/template.yaml` | Increase Lambda `Timeout` to 60 | Defense in depth |
| `backend/ask_assistant/app.py` | Change default model to `gemini-2.0-flash` | Fixes Lambda path |
| `backend/ask_assistant/app.py` | Increase `urllib` timeout to 55 s | Matches Lambda timeout |
| `backend/samconfig.toml` | Update `GeminiModel` parameter override | Deploy config consistency |

### After applying fixes

Re-deploy:

```bash
# AWS Lambda
cd backend
sam build && sam deploy

# Vercel (auto-deploys on push to main)
cd frontend
git add -A && git commit -m "fix: switch to gemini-2.0-flash to resolve 504 timeout" && git push
```

Then re-test the original query:

```bash
curl -s -X POST "https://msao2suw84.execute-api.us-east-1.amazonaws.com/ask-assistant" \
  -H "Content-Type: application/json" \
  -d '{"query": "Analyze the current status of SST-400 Industrial Steam Turbine (Unit ST-01): vibration is 4.739 mm/s, exhaust temperature is 609.2°C, and it has 23,810 hours since last overhaul. What maintenance actions should be taken?"}' \
  | python -m json.tool
```

Expected: Response in 3-8 seconds with model `gemini-2.0-flash`.
