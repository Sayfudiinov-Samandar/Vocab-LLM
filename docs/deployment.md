# Deployment Guide

## Environment Variables

Create these variables locally in `.env` and in the cloud platform:

```text
WEBHOOK_URL=https://your-public-domain.example
DATABASE_URL=sqlite:///./data/vocab.db
TAVILY_API_KEY=your-tavily-key
QWEN_API_KEY=your-qwen-key
QWEN_MODEL=qwen-plus
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_DELIVERY=polling
SECRET_KEY=change-this-in-production
```

Never submit real API keys, bot tokens, passwords, or private keys.

## Local Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open:

```text
http://localhost:8000
```

## Railway Deployment

1. Push the source code to a Git repository.
2. Create a Railway project.
3. Choose Dockerfile deployment.
4. Add the environment variables listed above.
5. Set `WEBHOOK_URL` to the Railway public HTTPS URL.
6. Confirm the health check:

```text
/api/health
```

## Telegram / OpenClaw Webhook

For local development, use polling:

```text
TELEGRAM_DELIVERY=polling
```

This lets your laptop receive `/start` and other Telegram messages without a public URL.

For public deployment, switch to webhook mode:

```text
TELEGRAM_DELIVERY=webhook
```

The backend sets the Telegram webhook on startup using:

```text
{WEBHOOK_URL}/telegram/webhook
```

`WEBHOOK_URL` must be a real public HTTPS URL. Telegram cannot call `localhost`, private IP addresses, fake domains, or unresolved hostnames.

For the final demo, show Telegram commands such as:

```text
add sanction
query sanction
review
quiz
```

## OpenClaw Gateway

The app also exposes an OpenClaw-compatible command gateway:

```text
POST /openclaw/gateway
```

Example local request:

```bash
curl -X POST http://localhost:8000/openclaw/gateway \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"query sanction\",\"telegram_id\":\"demo-user\"}"
```

Health endpoint:

```text
/openclaw/health
```

Onboarding endpoint:

```text
/openclaw/onboarding
```

Full onboarding guide:

```text
docs/openclaw-onboarding.md
```

The gateway supports the same command text used in Telegram:

```text
add WORD
query WORD
update WORD | notes
list
review
quiz
stats
delete WORD
```

## Public Access Checklist

- Web app loads on desktop.
- Web app loads on mobile.
- `/api/health` returns `{"status":"ok"}`.
- Telegram bot receives messages.
- Example Search Agent can save a real-source word.
- Source package excludes `.env`, `.venv`, `data/`, and local database files.
