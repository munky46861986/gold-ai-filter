# Gold AI Filter Bot

Web service Flask per filtrare i segnali TradingView prima di inviarli a Telegram.

## Render settings

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
gunicorn app:app
```

## Environment Variables

- `TELEGRAM_TOKEN`
- `CHAT_ID`
- `BIAS` = `AUTO` oppure `FORCE_BUY` oppure `FORCE_SELL`

## Webhook URL

Dopo il deploy su Render:
```text
https://NOME-SERVIZIO.onrender.com/webhook
```

## Test veloce

Apri:
```text
https://NOME-SERVIZIO.onrender.com/health
```