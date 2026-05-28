# INR ⇄ NPR Exchange Bot

A Telegram bot for semi-automatic currency exchange between Indian Rupees (INR) and Nepali Rupees (NPR).

## Features

- 💱 INR → NPR and NPR → INR exchange with live rates
- 💼 Built-in wallet system (load, exchange, withdraw)
- 📸 Payment screenshot + transaction ID verification
- 👤 User profiles, referral codes & referral bonus
- 📊 Transaction history and admin statistics
- 🔔 Real-time admin notifications for every request
- 📣 Admin broadcast to all users
- 🚫 User ban/unban
- 🔄 Auto-update from upstream repo (optional)

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/SunilSharmaNP/exchanger
cd exchanger
cp sample.env .env
# Edit .env with your real BOT_TOKEN and ADMIN_IDS
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
python bot.py
```

The database is created automatically on first run in `database/exchange_bot.db`.

---

## Docker

```bash
docker build -t exchangebot .
docker run -d --name exchangebot --env-file .env -e IN_DOCKER=1 exchangebot
```

---

## Deploy to Heroku

> ⚠️ **SQLite limitation:** Heroku's filesystem is ephemeral — the SQLite database resets on each dyno restart/deploy. For production, use a hobby dyno and accept periodic resets, or migrate to PostgreSQL.

### Option A — Git deploy (recommended)

```bash
heroku login
heroku create your-app-name
heroku config:set BOT_TOKEN=your_token ADMIN_IDS=your_id
heroku config:set UPI_ID=business@upi ESEWA_ID=esewa@merchant
heroku config:set IN_DOCKER=1
git subtree push --prefix exchanger heroku main
# OR if this repo IS the bot root:
git push heroku main
heroku ps:scale web=0 worker=1
```

### Option B — Deploy button

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

### Required config vars

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `ADMIN_IDS` | Comma-separated admin Telegram IDs |
| `UPI_ID` | UPI ID for payments (India) |
| `ESEWA_ID` | eSewa ID for payments (Nepal) |
| `IN_DOCKER` | Set to `1` on Heroku/containers |

---

## Admin Commands

| Command | Description |
|---|---|
| `/admin` | Open admin panel |
| `/credit add\|set <user> <INR\|NPR> <amount>` | Adjust user wallet |
| `/balance <user>` | View user wallet balances |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/restart` | Pull latest code and restart |

## User Commands

| Command | Description |
|---|---|
| `/start` | Main menu |
| `/help` | Help & commands |
| `/profile` | View your profile |
| `/wallet` | Check wallet balances |
| `/load` | Load funds into wallet |
| `/history` | Recent transaction history |
| `/withdraw` | Withdraw funds |

## Referral Links

Share your referral link: `https://t.me/YOUR_BOT_USERNAME?start=ref_YOURCODE`

When a referred user completes their first approved exchange, the referrer automatically receives a configurable bonus (default 1%).

---

## Environment Variables

See `sample.env` for the full list of configurable options.

## Stack

- Python 3.11
- aiogram 3.3 (async Telegram bot framework)
- SQLite (via stdlib `sqlite3`)
- python-dotenv
