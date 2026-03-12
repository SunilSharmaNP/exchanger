# INR ⇄ NPR Exchange Bot

This bot handles semi-automatic currency exchanges between INR and NPR.

Quick start

1. Create `.env` with `BOT_TOKEN` and `ADMIN_IDS`.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Initialize database and run:

```bash
python bot.py
```

Docker

```bash
docker build -t exchangebot:latest .
docker run -d --name exchangebot --env-file .env exchangebot:latest
```

Systemd

Copy `deployment/exchangebot.service` to `/etc/systemd/system/`, update paths, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now exchangebot.service
```

Testing

Run unit tests:

```bash
pytest -q
```
