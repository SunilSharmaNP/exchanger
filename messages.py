"""
Modern Telegram Messages Template with Expandable Blockquotes and Emojis.
Supports Telegram Bot API 7.0+ <blockquote> and <blockquote expandable>.
100% Clean, Concise & Professional English.
"""

WELCOME_MESSAGE = """
✨ <b>INR ⇄ NPR Exchange Hub</b> 🇮🇳 ⇄ 🇳🇵

<blockquote>
⚡ <b>Instant & Secure Cross-Border Remittance</b>
Best exchange rates with automated escrow protection.
</blockquote>

<b>💹 Live Exchange Rates:</b>
<blockquote>
🇮🇳 <b>1 INR  =  {inr_to_npr} NPR</b> 🇳🇵
🇳🇵 <b>1 NPR  =  {npr_to_inr} INR</b> 🇮🇳
</blockquote>
📌 <b>Service Fee:</b> <code>{fee}%</code> | <b>Min:</b> ₹100 / ₨100

<blockquote expandable>
🌟 <b>Key Features:</b>
• <b>Quick Remittance:</b> UPI to eSewa & eSewa to UPI
• <b>Dual Wallet:</b> Store & swap INR / NPR instantly
• <b>1% Lifetime Referral:</b> Earn on every friend exchange
• <b>Escrow Safety:</b> 100% refund on unfulfilled orders
• <b>24/7 Support:</b> In-app ticketing desk
</blockquote>

<i>👇 Select an option from the menu below:</i>
"""

EXCHANGE_STARTED = """
💱 <b>Select Exchange Direction</b>

<blockquote>
• <b>INR → NPR:</b> Send INR via UPI ➔ Receive NPR via eSewa
• <b>NPR → INR:</b> Send NPR via eSewa ➔ Receive INR via UPI
</blockquote>
"""

ENTER_AMOUNT = """
💰 <b>Enter Exchange Amount</b>

<blockquote>
<b>Allowed Range:</b> Min <code>100</code> | Max <code>100,000</code>
</blockquote>

<i>👇 Tap a quick amount button or type manually:</i>
"""

EXCHANGE_SUMMARY = """
📊 <b>Exchange Summary</b>

<blockquote>
<b>Send:</b> <code>{amount} {from_currency}</code>
<b>Rate:</b> <code>1 {from_currency} = {rate} {to_currency}</code>
<b>Gross Total:</b> <code>{calculated_amount} {to_currency}</code>
<b>Fee ({fee_percent}%):</b> <code>-{service_fee} {to_currency}</code>
</blockquote>

<blockquote expandable>
🎉 <b>You Receive:</b>
👉 <b>{final_amount} {to_currency}</b>

🔒 Rate locked for 15 minutes. Funds dispatched after payment verification.
</blockquote>

<i>Tap <b>"✅ Confirm & Proceed"</b> below:</i>
"""

PAYMENT_INSTRUCTIONS = """
💳 <b>Payment Instructions</b>

<blockquote>
<b>Amount to Transfer:</b> <code>{amount} {from_currency}</code>
</blockquote>

<blockquote expandable>
<b>🇮🇳 Indian Rupee (UPI Payment):</b>
UPI VPA: <code>{upi_id}</code>
<i>(Google Pay, PhonePe, Paytm, BHIM)</i>

<b>🇳🇵 Nepali Rupee (eSewa Payment):</b>
eSewa ID: <code>{esewa_id}</code>
<i>(eSewa Mobile Wallet)</i>
</blockquote>

<blockquote expandable>
⚠️ <b>Important Steps:</b>
1️⃣ Put your User ID <code>{user_id}</code> in the payment remarks/note.
2️⃣ Take a clear screenshot of completed transaction.
3️⃣ Tap <b>"✅ I Have Paid"</b> below to submit proof.
</blockquote>
"""

PAYMENT_VERIFICATION = """
📸 <b>Payment Verification</b>

<blockquote>
<b>Step 1:</b> Upload a clear payment screenshot.
<b>Step 2:</b> Submit 12-digit UTR / Reference ID.
</blockquote>

<i>Please upload your <b>Payment Screenshot (Photo)</b> now:</i>
"""

PAYMENT_ASK_TXN_ID = """
🔢 <b>Enter Transaction ID / UTR</b>

<blockquote>
Send your 12-digit Bank UTR or eSewa Reference ID:
<i>(e.g., 429019283011 or ESEWA9812304)</i>
</blockquote>
"""

ADMIN_REQUEST = """
🔔 <b>New Exchange Order — #{request_id}</b>

<blockquote>
<b>User:</b> <a href="tg://user?id={user_id}">@{username}</a> (<code>{user_id}</code>)
<b>Type:</b> <b>{exchange_type}</b>
<b>Sent:</b> <code>{amount}</code> | <b>Rate:</b> <code>{rate}</code>
<b>Payout:</b> <code>{final_amount} {to_currency}</code>
<b>UTR / Txn ID:</b> <code>{transaction_id}</code>
</blockquote>

<blockquote expandable>
📋 <b>User Snapshot:</b>
• Total Exchanges: <code>{total_exchanges}</code> | Volume: <code>{total_volume}</code>
• Wallet: INR ₹{wallet_inr} | NPR ₨{wallet_npr}
</blockquote>

<i>Screenshot attached. Verify in bank before approving:</i>
"""

APPROVED_MESSAGE = """
🎉 <b>Order #{request_id} Approved!</b>

<blockquote>
<b>Payout Amount:</b> <b>{final_amount} {to_currency}</b>
<b>Status:</b> ⏳ Processing Transfer...
<b>ETA:</b> 5–15 minutes
</blockquote>

<i>Transfer is being sent to your destination account. Thank you! 🙏</i>
"""

COMPLETED_MESSAGE = """
✅ <b>Transaction Completed — #{request_id}</b>

<blockquote>
<b>Sent:</b> <code>{sent_amount} {from_currency}</code>
<b>Received:</b> <code>{received_amount} {to_currency}</code>
<b>Fee:</b> <code>{service_fee} {to_currency}</code>
<b>Date:</b> <code>{timestamp}</code>
<b>Status:</b> <b>COMPLETED</b>
</blockquote>

<blockquote expandable>
💡 <b>Earn 1% Lifetime Bonus:</b>
Invite friends and earn 1% bonus on all their trades!
Go to <b>"👤 Profile & Referrals"</b> for your invite link.
</blockquote>
"""

REJECTED_MESSAGE = """
❌ <b>Order #{request_id} Rejected</b>

<blockquote>
<b>Reason:</b> <b>{reason}</b>
</blockquote>

<blockquote expandable>
🛡️ <b>Refund & Security:</b>
• Any debited/held wallet funds have been <b>auto-refunded</b>.
• If payment was made correctly, tap <b>"📞 Contact Support"</b> below.
</blockquote>
"""

CURRENT_RATE = """
💹 <b>Live Exchange Rates</b>

<blockquote>
🇮🇳 <b>1 INR  =  {inr_to_npr} NPR</b> 🇳🇵
🇳🇵 <b>1 NPR  =  {npr_to_inr} INR</b> 🇮🇳
</blockquote>

<blockquote expandable>
📌 <b>Policy:</b>
• Service Fee: <b>{fee}%</b>
• Allowed Range: ₹100 – ₹100,000
• Updated continuously based on market & NRB standards.
</blockquote>
"""

CALCULATOR_RESULT = """
🔢 <b>Rate Calculator Result</b>

<blockquote>
<b>Input:</b> <code>{amount} {from_currency}</code>
<b>Rate:</b> <code>1 {from_currency} = {rate} {to_currency}</code>
</blockquote>

<blockquote expandable>
<b>Gross:</b> <code>{gross} {to_currency}</code>
<b>Fee ({fee_percent}%):</b> <code>-{fee} {to_currency}</code>
━━━━━━━━━━━━━━━━━
👉 <b>Net Payout:</b> <b>{final} {to_currency}</b>
</blockquote>

<i>Tap <b>"💱 Exchange Now"</b> to start remittance:</i>
"""

WALLET_MENU = """
💼 <b>My Digital Wallet</b>

<blockquote>
🇮🇳 <b>INR Balance:</b> <code>₹{wallet_inr}</code>
🇳🇵 <b>NPR Balance:</b> <code>₨{wallet_npr}</code>
</blockquote>

<blockquote expandable>
⚡ <b>Wallet Advantages:</b>
• Instant swaps with zero admin review delays.
• Quick deposit & withdrawal to UPI or eSewa.
• Referral bonuses credited directly here.
</blockquote>
"""

TRANSACTION_HISTORY = """
📜 <b>Transaction History</b>

<blockquote expandable>
{transactions}
</blockquote>

<blockquote>
<b>Total Completed:</b> <code>{total} txn(s)</code>
<b>Total Volume:</b> <code>{total_amount}</code>
</blockquote>
"""

HOW_IT_WORKS = """
📚 <b>How It Works</b>

<blockquote expandable>
<b>1️⃣ Select Direction & Amount:</b>
Choose INR ➔ NPR or NPR ➔ INR. Review live rate and net payout.

<b>2️⃣ Transfer Payment:</b>
Pay to the displayed UPI VPA (India) or eSewa ID (Nepal).

<b>3️⃣ Upload Proof:</b>
Send payment screenshot and 12-digit UTR / Reference ID.

<b>4️⃣ Payout Dispatched:</b>
Admin verifies and transfers funds to you within 5–15 minutes.

<b>5️⃣ Instant Wallet:</b>
Keep funds in bot wallet for instant conversion anytime!
</blockquote>
"""

PROFILE_MESSAGE = """
👤 <b>User Profile</b>

<blockquote>
<b>Name:</b> {first_name}
<b>Username:</b> @{username}
<b>User ID:</b> <code>{user_id}</code>
<b>Joined:</b> <code>{joined_date}</code>
</blockquote>

<blockquote expandable>
💼 <b>Wallet Balances:</b>
• INR: <b>₹{wallet_inr}</b> | NPR: <b>₨{wallet_npr}</b>

📊 <b>Trading Stats:</b>
• Completed Exchanges: <b>{total_exchanges}</b>
• Total Volume: <b>{total_amount}</b>
</blockquote>

<blockquote expandable>
🎁 <b>Referral Program (Earn 1%):</b>
• Referral Code: <code>{referral_code}</code>
• Referral Link:
<code>{referral_link}</code>
• Referred Users: <b>{referred_count}</b>
</blockquote>
"""

SUPPORT_MENU = """
📞 <b>Support Helpdesk</b>

<blockquote expandable>
<b>❓ FAQ:</b>
• <b>Verification Time:</b> 5–15 minutes during active hours.
• <b>Funds Safety:</b> 100% escrow protection with auto-refund.
• <b>Fee:</b> 2.5% platform gateway fee.
</blockquote>

<i>👇 Open a ticket or contact support below:</i>
"""

SUPPORT_TICKET_CREATED = """
🎟️ <b>Support Ticket #{ticket_id} Created</b>

<blockquote expandable>
Your ticket has been sent to our support desk.
Expected response time: <b>15–30 minutes</b>.
You will receive reply notifications directly here.
</blockquote>
"""

ADMIN_STATS = """
📊 <b>Platform Analytics</b>

<blockquote>
<b>👥 Users:</b> Total: <code>{total_users}</code> | New: <code>{new_users}</code> | Active: <code>{active_today}</code>
<b>💱 Orders:</b> Total: <code>{total_transactions}</code> | ✅ <code>{completed}</code> | ⏳ <code>{pending}</code> | ❌ <code>{rejected}</code>
</blockquote>

<blockquote expandable>
<b>💰 Volume:</b>
• INR: <code>{total_inr}</code> | NPR: <code>{total_npr}</code>
• Total Fee Earnings: <code>{total_fees}</code>

<b>💹 Rates:</b>
• INR→NPR: <code>{inr_to_npr}</code> | NPR→INR: <code>{npr_to_inr}</code>
• Open Tickets: <code>{open_tickets}</code>
</blockquote>
"""

ABOUT_US_MESSAGE = """
🏢 <b>About Us — INR ⇄ NPR Remittance Hub</b> 🇮🇳 ⇄ 🇳🇵

<blockquote>
⚡ <b>Our Mission:</b>
Secure, transparent, and ultra-fast cross-border remittance between India and Nepal.
Designed for students, workers, merchants, and tourists for hassle-free money transfers.
</blockquote>

<blockquote expandable>
🛡️ <b>Security & Guarantees:</b>
• <b>100% Escrow Protection:</b> Unfulfilled orders are auto-refunded to your wallet.
• <b>Zero Hidden Fees:</b> Flat 2.5% fee clearly displayed before confirmation.
• <b>Direct Payment Rails:</b> Native UPI (PhonePe, GPay, Paytm) & eSewa integration.
• <b>Fast Dispatch:</b> Average payout within 5–15 minutes.
• <b>Dual Wallet:</b> Instant self-conversion 24/7/365.
</blockquote>
"""

CONTACT_US_MESSAGE = """
📞 <b>Contact & Support Hub</b> 🇮🇳 ⇄ 🇳🇵

<blockquote>
Need help with an order, payment, or wallet balance? Our team is ready to assist.
</blockquote>

<blockquote expandable>
💬 <b>Official Support Channels:</b>
• <b>In-Bot Ticket:</b> Type <code>/support</code> or tap '📞 Contact Support'
• <b>Telegram Admin:</b> <a href="https://t.me/SunilSharmaNP">@SunilSharmaNP</a>
• <b>Operating Hours:</b> 8:00 AM – 11:00 PM IST / NPT (Daily)
• <b>Automated Wallet:</b> Available 24/7/365
</blockquote>

<blockquote expandable>
⚠️ <b>Security Notice:</b>
• Support will NEVER request your password, PIN, or OTP.
• Only transfer funds to details displayed inside this official bot.
</blockquote>
"""

ERROR_MESSAGES = {
    "invalid_amount": "❌ Please enter a valid amount between ₹100 and ₹100,000.",
    "amount_too_low": "❌ Minimum exchange amount is 100.",
    "amount_too_high": "❌ Maximum exchange amount is 100,000.",
    "anti_spam": "⏱️ Too many requests! Please wait {wait_time} minute(s).",
    "banned": "🚫 Your account is suspended. Contact support for assistance.",
    "database_error": "⚠️ Database error. Please try again shortly.",
    "invalid_input": "❌ Invalid input. Please try again.",
}

SUCCESS_MESSAGES = {
    "payment_received": "✅ Payment proof received! Admin will verify shortly.",
    "exchange_completed": "🎉 Exchange completed successfully!",
}
