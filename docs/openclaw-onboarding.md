# OpenClaw Onboarding Guide

This guide explains how to onboard the AI Vocabulary Assistant with OpenClaw-style command handling and Telegram.

## 1. What Is Already Implemented

The project has three OpenClaw-related pieces:

- `config/openclaw/config.yaml`: declares the project, Telegram platform, gateway endpoints, command patterns, LLM, search, and database integrations.
- `backend/openclaw_wrapper.py`: initializes OpenClaw metadata and records whether the installed OpenClaw runtime is available.
- `backend/openclaw_gateway.py`: exposes an OpenClaw-compatible command gateway at `/openclaw/gateway`.

Telegram and gateway commands both call the same backend workflow:

```text
Command text
  -> Parse command
  -> Run agent or database action
  -> Save/query/update/delete data
  -> Return result
  -> Print numbered OpenClaw terminal steps
```

## 2. Required Environment Variables

Create `.env` from `.env.example`.

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

Use these delivery modes:

```text
polling  = local Telegram testing
webhook  = public deployment with HTTPS
disabled = backend-only checks
```

## 3. Local Onboarding

Install and start the backend:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open the web app:

```text
http://localhost:8000
```

Check OpenClaw health:

```text
http://localhost:8000/openclaw/health
```

Check onboarding metadata:

```text
http://localhost:8000/openclaw/onboarding
```

## 4. Test The OpenClaw Gateway

PowerShell examples:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/openclaw/gateway" `
  -ContentType "application/json" `
  -Body '{"text":"stats","telegram_id":"demo-user"}'
```

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/openclaw/gateway" `
  -ContentType "application/json" `
  -Body '{"text":"list","telegram_id":"demo-user"}'
```

When API keys are ready:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/openclaw/gateway" `
  -ContentType "application/json" `
  -Body '{"text":"add sanction","telegram_id":"demo-user"}'
```

Expected terminal trace:

```text
[OpenClaw][gateway] 1/5 Receive gateway text: add sanction
[OpenClaw][gateway] 2/5 Resolve gateway user_id=...
[OpenClaw][gateway] 3/5 Parse command='add', argument='sanction'
[OpenClaw][gateway] 4/5 Run Example Search Agent
[ExampleSearchAgent] 1/8 Normalize and validate input word: sanction
[ExampleSearchAgent] 2/8 Check database for existing word: sanction
[ExampleSearchAgent] 3/8 Search authentic English sources with Tavily: sanction
...
[OpenClaw][gateway] 5/5 Return add result
```

## 5. Telegram Onboarding

1. Create or reset the bot token in BotFather.
2. Put the token in `.env` as `TELEGRAM_BOT_TOKEN`.
3. Set local mode:

```text
TELEGRAM_DELIVERY=polling
```

4. Start the backend.
5. Open Telegram and send:

```text
/start
```

6. Test commands:

```text
add sanction
query sanction
update sanction | final project demo word
list
review
quiz
stats
delete sanction
```

Expected terminal trace for Telegram:

```text
[OpenClaw][message] 1/4 Receive Telegram/OpenClaw text: add sanction
[OpenClaw][message] 2/4 Map Telegram user to internal user_id=...
[OpenClaw][message] 3/4 Parse command='add', argument='sanction'
[OpenClaw][add] 1/6 Receive add command for word='sanction'
[OpenClaw][add] 2/6 Create ExampleSearchAgent workflow
[OpenClaw][add] 3/6 Run search -> extract -> enrich -> save pipeline
...
[OpenClaw][add] 6/6 Send added-word response to Telegram
```

## 6. Public Deployment Onboarding

After deploying to Railway, Render, or another public HTTPS platform:

1. Set `WEBHOOK_URL` to the public domain.

```text
WEBHOOK_URL=https://your-real-public-domain
```

2. Set:

```text
TELEGRAM_DELIVERY=webhook
```

3. Restart the deployed app.
4. The app will set Telegram webhook:

```text
{WEBHOOK_URL}/telegram/webhook
```

5. Public OpenClaw gateway:

```text
{WEBHOOK_URL}/openclaw/gateway
```

6. Public OpenClaw health:

```text
{WEBHOOK_URL}/openclaw/health
```

## 7. Demo Script

Use this order in your final video:

```text
1. Show config/openclaw/config.yaml
2. Start backend and show "OpenClaw initialized: telegram"
3. Open /openclaw/health
4. Send /start in Telegram
5. Send add sanction
6. Show terminal numbered OpenClaw and ExampleSearchAgent steps
7. Open web dashboard and show the saved word
8. Run query sanction
9. Run review and quiz
10. Explain public webhook deployment
```

## 8. Troubleshooting

If `/start` does not work locally:

```text
TELEGRAM_DELIVERY must be polling
```

If webhook fails:

```text
WEBHOOK_URL must be real public HTTPS, not localhost
```

If `add WORD` fails:

```text
Check TAVILY_API_KEY and QWEN_API_KEY
```

If the bot token was pasted into screenshots, chat, or logs:

```text
Regenerate the token in BotFather before submission
```
