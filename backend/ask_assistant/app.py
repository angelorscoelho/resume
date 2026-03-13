"""
Siemens Energy — Gas Turbine AI Maintenance Assistant
Lambda handler: /ask-assistant  (POST)

Real RAG Pipeline (S3 + Gemini Embeddings + Cosine Similarity)
--------------------------------------------------------------
1. Receive user query via POST body {"query": "..."}
2. Embed the query using Google text-embedding-004 (768-dim vector)
3. Download pre-computed chunk embeddings from S3 (single JSON manifest)
4. Rank chunks by cosine similarity; inject top-K into the system prompt
5. Call gemini-2.0-flash with the grounded context
6. Return {"answer": "...", "sources": [...], "model": "..."} to the client

No external SDK required — both APIs called via stdlib urllib.

S3 knowledge base layout
-------------------------
  s3://{S3_BUCKET_NAME}/chunks/embeddings.json
      -> JSON array of objects:
          { "id": str, "text": str, "embedding": [float, ...], "metadata": {...} }

Run ingest_manuals.py once locally to populate the bucket before first use.

Environment variables (set via SAM template.yaml)
--------------------------------------------------
  GEMINI_API_KEY  -- Google AI Studio / Vertex AI key
  GEMINI_MODEL    -- chat model (default: gemini-2.0-flash)
  S3_BUCKET_NAME  -- bucket containing chunks/embeddings.json
  RAG_TOP_K       -- number of chunks to retrieve (default: 3)
"""

import json
import math
import os
import logging
import time
import urllib.request
import urllib.error

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants
EMBEDDING_MODEL = "text-embedding-004"       # Google 768-dim embedding model
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
S3_EMBEDDINGS_KEY = "chunks/embeddings.json" # single manifest downloaded per request
DEFAULT_TOP_K = 3                            # context chunks injected into the prompt

SYSTEM_PROMPT = (
    "You are an expert gas turbine maintenance engineer at Siemens Energy. "
    "You are given retrieved excerpts from the official Siemens SGT-series Maintenance Manual "
    "as [CONTEXT] below. Answer the question using ONLY the provided context. "
    "When the question involves a RISK or NOK status alert, produce a structured action plan "
    "with numbered steps and estimated timeframes. "
    "If the context is insufficient, state clearly what additional manual section should be consulted. "
    "Use precise engineering terminology appropriate for a field maintenance technician."
)

# S3 client (module-level for Lambda container reuse)
_s3 = boto3.client("s3")

# /tmp cache for embeddings (persists across warm invocations)
_cached_chunks: list | None = None
_cached_bucket: str | None = None


# Vector helpers

def _dot(a: list, b: list) -> float:
    """Dot product of two equal-length vectors."""
    return sum(x * y for x, y in zip(a, b))


def _norm(v: list) -> float:
    """L2 norm of a vector."""
    return math.sqrt(sum(x * x for x in v))


def _cosine_similarity(a: list, b: list) -> float:
    """Cosine similarity between two vectors. Returns 0.0 on zero-norm input."""
    denom = _norm(a) * _norm(b)
    return _dot(a, b) / denom if denom else 0.0


# RAG retrieval

def _embed_query(api_key: str, query: str) -> list:
    """
    Embed a user query with Google text-embedding-004.
    Returns a 768-dimensional float vector via the Gemini REST API.
    """
    url = f"{GEMINI_API_BASE}/{EMBEDDING_MODEL}:embedContent?key={api_key}"
    payload = json.dumps({
        "model": f"models/{EMBEDDING_MODEL}",
        "content": {"parts": [{"text": query}]},
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["embedding"]["values"]


def _load_chunks_from_s3(bucket: str) -> list:
    """
    Download the pre-computed embeddings manifest from S3.
    Uses /tmp file cache so subsequent warm invocations skip the download.
    The manifest is a JSON array of chunk objects:
      [{"id": "...", "text": "...", "embedding": [...], "metadata": {...}}, ...]
    """
    global _cached_chunks, _cached_bucket

    # Return in-memory cache if available for same bucket
    if _cached_chunks is not None and _cached_bucket == bucket:
        logger.info("Using in-memory cached embeddings (%d chunks).", len(_cached_chunks))
        return _cached_chunks

    # Check /tmp file cache
    tmp_path = "/tmp/embeddings.json"
    if os.path.exists(tmp_path) and _cached_bucket == bucket:
        logger.info("Loading embeddings from /tmp cache.")
        with open(tmp_path, "r", encoding="utf-8") as f:
            _cached_chunks = json.load(f)
        _cached_bucket = bucket
        logger.info("Loaded %d chunks from /tmp cache.", len(_cached_chunks))
        return _cached_chunks

    # Download from S3
    logger.info("Downloading embeddings manifest from s3://%s/%s", bucket, S3_EMBEDDINGS_KEY)
    obj = _s3.get_object(Bucket=bucket, Key=S3_EMBEDDINGS_KEY)
    raw = obj["Body"].read().decode("utf-8")
    _cached_chunks = json.loads(raw)
    _cached_bucket = bucket
    logger.info("Loaded %d chunks from S3.", len(_cached_chunks))

    # Write to /tmp for persistence across warm invocations
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(raw)
        logger.info("Cached embeddings to %s.", tmp_path)
    except OSError as exc:
        logger.warning("Failed to cache embeddings to /tmp: %s", exc)

    return _cached_chunks


def _retrieve_top_k(query_embedding: list, chunks: list, top_k: int) -> list:
    """
    Score every chunk by cosine similarity to the query embedding,
    return the top_k chunks sorted by descending score.
    Pure Python -- no NumPy, no additional dependencies.
    """
    scored = [
        {**chunk, "_score": _cosine_similarity(query_embedding, chunk["embedding"])}
        for chunk in chunks
    ]
    scored.sort(key=lambda c: c["_score"], reverse=True)
    return scored[:top_k]


# Gemini chat

def _call_gemini_chat(api_key: str, model: str, context_text: str, query: str) -> str:
    """
    Call the Gemini generateContent REST endpoint with retrieved context.
    Uses stdlib urllib -- zero external dependencies.
    gemini-2.0-flash is the default: fast responses suitable for structured
    maintenance queries within Lambda timeout limits.
    """
    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
    user_message = (
        f"[CONTEXT -- retrieved from Siemens SGT Maintenance Manual]\n"
        f"{context_text}\n\n"
        f"[QUESTION]\n{query}"
    )
    payload = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1200,
            "candidateCount": 1,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HARASSMENT",         "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",        "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",  "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=50) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    candidates = body.get("candidates", [])
    if not candidates:
        raise ValueError(f"Gemini returned no candidates. Response: {body}")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError("Gemini candidate has no text parts.")
    return parts[0].get("text", "").strip()


# CORS helpers

def _build_cors_headers(event: dict) -> dict:
    """Return CORS headers. Echoes the request Origin if present."""
    origin = (event.get("headers") or {}).get("origin", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }


def _error(status: int, message: str, headers: dict) -> dict:
    logger.warning("Returning error %d: %s", status, message)
    return {
        "statusCode": status,
        "headers": {**headers, "Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }


# Lambda entry point

def lambda_handler(event: dict, context) -> dict:  # noqa: ANN001
    start = time.time()
    cors_headers = _build_cors_headers(event)

    # Handle CORS preflight
    if event.get("requestContext", {}).get("http", {}).get("method", "").upper() == "OPTIONS":
        return {"statusCode": 200, "headers": cors_headers, "body": ""}

    # Parse request body
    try:
        body = json.loads(event.get("body") or "{}")
        query = body.get("query", "").strip()
        if not query:
            return _error(400, "Missing 'query' field in request body.", cors_headers)
    except json.JSONDecodeError as exc:
        return _error(400, f"Invalid JSON body: {exc}", cors_headers)

    logger.info("Received query (first 120 chars): %s", query[:120])

    # Read environment configuration
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is not set.")
        return _error(500, "Server configuration error: Gemini API key not set.", cors_headers)

    chat_model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    bucket = os.environ.get("S3_BUCKET_NAME", "")
    if not bucket:
        logger.error("S3_BUCKET_NAME environment variable is not set.")
        return _error(500, "Server configuration error: S3 bucket name not set.", cors_headers)

    top_k = int(os.environ.get("RAG_TOP_K", DEFAULT_TOP_K))

    # Determine remaining time budget (leave 3 s buffer for response serialization)
    timeout_budget = 60 - 3  # Lambda timeout minus buffer for response serialization
    if context and hasattr(context, "get_remaining_time_in_millis"):
        timeout_budget = (context.get_remaining_time_in_millis() / 1000) - 3

    try:
        # Step 1: Embed the user query
        logger.info("Embedding query with %s...", EMBEDDING_MODEL)
        query_embedding = _embed_query(api_key, query)
        print(f"Step 1 (embed query) took {time.time() - start:.2f}s")

        if time.time() - start > timeout_budget:
            return _error(504, "Request approaching timeout after embedding step.", cors_headers)

        # Step 2: Download chunk embeddings from S3
        chunks = _load_chunks_from_s3(bucket)
        print(f"Step 2 (S3 download) took {time.time() - start:.2f}s")

        if time.time() - start > timeout_budget:
            return _error(504, "Request approaching timeout after S3 download.", cors_headers)

        # Step 3: Cosine similarity -> top-K retrieval
        top_chunks = _retrieve_top_k(query_embedding, chunks, top_k)
        logger.info(
            "Top-%d chunks retrieved -- scores: %s",
            top_k,
            [round(c["_score"], 4) for c in top_chunks],
        )
        print(f"Step 3 (cosine retrieval) took {time.time() - start:.2f}s")

        # Build a single context block from the retrieved chunks
        context_text = "\n\n---\n\n".join(
            f"[Source: {c.get('metadata', {}).get('section', c['id'])}]\n{c['text']}"
            for c in top_chunks
        )

        if time.time() - start > timeout_budget:
            return _error(504, "Request approaching timeout before Gemini call.", cors_headers)

        # Step 4: Call Gemini chat
        logger.info("Calling Gemini chat model: %s", chat_model)
        answer = _call_gemini_chat(api_key, chat_model, context_text, query)
        print(f"Step 4 (Gemini chat) took {time.time() - start:.2f}s")
        logger.info("Answer generated successfully.")

    except urllib.error.HTTPError as exc:
        elapsed = time.time() - start
        print(f"HTTP error after {elapsed:.2f}s")
        error_body = exc.read().decode("utf-8", errors="replace")
        logger.exception("HTTP error %d: %s", exc.code, error_body)
        if exc.code in (401, 403):
            return _error(500, "Gemini authentication failed. Check your API key.", cors_headers)
        if exc.code == 429:
            return _error(429, "Gemini rate limit exceeded. Please retry after a moment.", cors_headers)
        return _error(502, f"Gemini API error {exc.code}. Please try again.", cors_headers)
    except (urllib.error.URLError, TimeoutError) as exc:
        elapsed = time.time() - start
        print(f"Timeout/URL error after {elapsed:.2f}s")
        logger.exception("Network error: %s", exc)
        return _error(504, "Request timed out while contacting AI service. Please retry.", cors_headers)
    except ValueError as exc:
        logger.exception("Value error: %s", exc)
        return _error(502, f"LLM service error: {exc}", cors_headers)
    except Exception as exc:  # noqa: BLE001
        elapsed = time.time() - start
        print(f"Unexpected error after {elapsed:.2f}s")
        logger.exception("Unexpected error in RAG pipeline: %s", exc)
        return _error(500, "Internal error in RAG pipeline. Please retry.", cors_headers)

    # Step 5: Return result
    total_elapsed = time.time() - start
    print(f"Total request took {total_elapsed:.2f}s")

    sources = [
        {
            "id": c["id"],
            "section": c.get("metadata", {}).get("section", ""),
            "score": round(c["_score"], 4),
            "preview": c["text"][:200] + ("\u2026" if len(c["text"]) > 200 else ""),
        }
        for c in top_chunks
    ]
    payload = {
        "answer": answer,
        "sources": sources,           # chunk provenance exposed to the frontend
        "model": chat_model,
        "embedding_model": EMBEDDING_MODEL,
        "top_k": top_k,
        "elapsed_seconds": round(total_elapsed, 2),
    }
    return {
        "statusCode": 200,
        "headers": {**cors_headers, "Content-Type": "application/json"},
        "body": json.dumps(payload),
    }
