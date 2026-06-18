# Hugging Face Spaces Backend Deploy

Deploy this backend as a Hugging Face **Docker Space**. The checked-in `Dockerfile`
starts FastAPI on port `7860`, which matches the Space `app_port`.

## 1. Create the Space

In Hugging Face, create a new Space:

```text
Space name: adaa-agent-backend
SDK: Docker
Branch: main
Visibility: Public or Private
```

## 2. Add Space Variables

Open the Space settings and add these variables:

```text
AUTODATA_ENV=production
AUTODATA_OLLAMA_BASE_URL=https://ollama.com
AUTODATA_OLLAMA_MODEL=qwen3-coder:480b
AUTODATA_OLLAMA_THINK=false
AUTODATA_OLLAMA_NUM_PREDICT=1200
AUTODATA_LLM_TIMEOUT_SECONDS=90
AUTODATA_EXECUTION_TIMEOUT_SECONDS=12
AUTODATA_MAX_REPAIR_ATTEMPTS=2
AUTODATA_CORS_ORIGINS=https://YOUR_NETLIFY_SITE.netlify.app
```

Add this as a **secret**:

```text
AUTODATA_OLLAMA_API_KEY=your_ollama_api_key
```

If you use a custom domain for Netlify, include it in `AUTODATA_CORS_ORIGINS`.
Multiple origins are comma-separated.

## 3. Push to the Space

Add the Hugging Face Space remote:

```bash
git remote add hf https://huggingface.co/spaces/YOUR_HF_USERNAME/adaa-agent-backend
git push hf main
```

Hugging Face will build the Docker image automatically.

## 4. Test the Backend

After the Space is running, open:

```text
https://YOUR_HF_USERNAME-adaa-agent-backend.hf.space/api/v1/health
```

Expected response:

```json
{"status":"ok","environment":"production","model":"qwen3-coder:480b"}
```

## 5. Point Netlify at the Backend

In Netlify frontend environment variables, set:

```text
VITE_API_BASE_URL=https://YOUR_HF_USERNAME-adaa-agent-backend.hf.space
```

Redeploy the Netlify frontend after saving the variable.
