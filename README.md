# 🇮🇳 ⇄ 🇳🇵 Professional INR ⇄ NPR Telegram Exchange Bot

Modern, secure, and production-grade currency remittance bot powered by **aiogram 3.x** and **Telegram Bot API 7.0+**.

---

## 🌟 Upgrades & Key Features

### 1. 🎨 Ultra-Modern UI/UX & Telegram 7.0+ Formatting
- **Expandable Blockquotes (`<blockquote expandable>`)**: Keeps all terms, order breakdowns, payment guidelines, and admin review cards sleek, collapsible, and uncluttered.
- **Concise & Professional Messages**: All messages are short, clear, and scannable with high-impact key details and no unnecessary walls of text.
- **Regular Reply Keyboard (Bottom Menu)**: Persistent, tap-friendly buttons directly on the Telegram screen for intuitive navigation.
- **Quick Amount Selectors**: Instant 1-tap buttons for `₹500`, `₹1,000`, `₹2,500`, `₹5,000`, `₹10,000`, `₹25,000`, or custom numeric input.

### 2. ⚡ Powerful In-Bot Modules
- **🔢 Live Rate Calculator (`/calc <amount>` or Menu Button)**: Instantly calculates exchange conversion, gross amount, service fee, and net payout without having to initiate a transaction.
- **📲 Dynamic UPI QR Code**: Automatically renders NPCI-compliant UPI QR codes for instant scanning via PhonePe, Google Pay, Paytm, or BHIM.
- **🔍 Real-Time Order Status Tracker (`/status <order_id>`)**: Track order progress with real-time review status badges.
- **🔎 Admin Super Search (`/find <query>`)**: Instant search across User IDs, usernames, UTR reference numbers, and orders.
- **🛡️ 1-Click Structured Rejections**: Admin can select specific pre-configured rejection reasons with automated wallet refund.
- **💼 Dual Digital Wallet**: Store and exchange balances between INR and NPR instantly without waiting for admin review.
- **🎁 1% Lifetime Referral Program**: Automatic 1% reward credited to referrers on friends' first completed remittance.

### 3. 🛡️ Security & Reliability Architecture
- **HTML Parse Error Protection**: All dynamic user-generated text is sanitized with `safe_html` to prevent Telegram markup crashes.
- **Race Condition & Double-Spend Prevention**: Atomic database balance deductions (`UPDATE users SET wallet = wallet - ? WHERE wallet >= ?`).
- **SQLite Concurrency Hardening**: WAL (Write-Ahead Logging) mode, `synchronous=NORMAL`, and `busy_timeout=30000ms`.
- **Responsive Callbacks**: Immediate `callback.answer()` prevents Telegram loading spinners from freezing.

---

## 🚀 Installation & Quick Start

### 1. Requirements
- Python 3.10+
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### 2. Install Dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configuration (`.env`):
Copy `sample.env` to `.env` and fill in your credentials:
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS=123456789
UPI_ID=merchant@okaxis
ESEWA_ID=9801234567
SERVICE_FEE_PERCENTAGE=2.5
ENABLE_DYNAMIC_QR=true
```

### 4. Run the Bot:
```bash
python bot.py
```

---

## 📂 File Architecture
- `bot.py` - Bot entrypoint, command registrations, and dispatcher polling loop.
- `handlers.py` - State machines, quick amount grids, exchange workflow, calculator, and admin handlers.
- `database.py` - WAL-enabled SQLite database, atomic wallet operations, indexing, and search engine.
- `keyboards.py` - Regular reply keyboards, quick amount buttons, and admin inline approval panels.
- `messages.py` - Concise, professional English templates with Telegram 7.0+ blockquotes.
- `utils.py` - UPI QR generator, amount validator, UTR validator, currency formatting, and anti-spam controls.
- `config.py` - Central configuration, environment variables, and fallback settings.
- `log_channel.py` - Structured real-time event logging to Telegram channels.
- `errors.py` - Global exception and error handling middleware.
