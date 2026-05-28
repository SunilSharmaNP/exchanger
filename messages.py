WELCOME_MESSAGE = """
🌍 <b>INR ⇄ NPR Exchange</b>

Your trusted platform for fast, secure currency exchange between India and Nepal.

<b>💹 Live Rates:</b>
• 1 INR = <b>{inr_to_npr} NPR</b>
• 1 NPR = <b>{npr_to_inr} INR</b>

<b>✨ What you can do:</b>
• 💱 Exchange INR ↔ NPR instantly
• 💰 Load &amp; manage your wallet
• 💸 Withdraw anytime
• 📊 Full transaction history
• 💬 Live support chat

<i>All transactions are secured and verified by our admin team.</i>
"""

EXCHANGE_STARTED = """
💱 <b>Select Exchange Direction</b>

Choose which currency you want to convert:
"""

ENTER_AMOUNT = """
💰 <b>Enter Amount</b>

Please enter the amount you want to exchange:

<b>Limits:</b>
• Minimum: ₹100 / ₨100
• Maximum: ₹1,00,000 / ₨1,00,000

<i>Type the number and press Send (e.g. 5000)</i>
"""

EXCHANGE_SUMMARY = """
📊 <b>Exchange Summary</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>
You send:       <b>{amount} {from_currency}</b>
Rate:           <b>1 {from_currency} = {rate} {to_currency}</b>
Gross amount:   <b>{calculated_amount} {to_currency}</b>
Service fee ({fee_percent}%): <b>- {service_fee} {to_currency}</b>
<b>You receive:    {final_amount} {to_currency}</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>

<i>Please review carefully before confirming.</i>
"""

PAYMENT_INSTRUCTIONS = """
💳 <b>Payment Instructions</b>

Send <b>exactly</b> the amount shown in your exchange summary.

<b>🇮🇳 UPI (India):</b>
<code>{upi_id}</code>

<b>🇳🇵 eSewa (Nepal):</b>
<code>{esewa_id}</code>

<b>⚠️ Important:</b>
• Use <code>{user_id}</code> as payment reference/note
• Take a screenshot immediately after payment
• Click <b>"I Have Paid"</b> only after payment is sent

<i>Payments are verified within 5–10 minutes.</i>
"""

PAYMENT_VERIFICATION = """
✅ <b>Payment Verification</b>

Please complete both steps below:

<b>Step 1 📸</b> — Upload your payment screenshot
<b>Step 2 🔢</b> — Send the transaction ID

<i>Make sure the screenshot clearly shows the amount and date.</i>
"""

ADMIN_REQUEST = """
🔔 <b>New Request — #{request_id}</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>User:</b>   <a href="tg://user?id={user_id}">@{username}</a> (<code>{user_id}</code>)
<b>Type:</b>   {exchange_type}
<b>Sends:</b>  {amount}
<b>Rate:</b>   {rate}
<b>Receives:</b> {final_amount} {to_currency}
<b>Txn ID:</b> <code>{transaction_id}</code>
<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>

<i>Screenshot is attached above. Approve or reject below.</i>
"""

APPROVED_MESSAGE = """
✅ <b>Request #{request_id} — Approved!</b>

Great news! Your exchange request has been approved.

<b>You will receive:</b> <b>{final_amount} {to_currency}</b>
<b>Status:</b> ⏳ Processing payout…

You'll get a confirmation once payment is sent to you.
<i>Estimated time: 5–15 minutes</i>
"""

COMPLETED_MESSAGE = """
🎉 <b>Transaction Completed — #{request_id}</b>

Your exchange has been successfully processed.

<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>Sent:</b>      {sent_amount} {from_currency}
<b>Received:</b>  {received_amount} {to_currency}
<b>Fee:</b>       {service_fee} {to_currency}
<b>Completed:</b> {timestamp}
<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>

<i>Thank you for using our service! 🙏</i>
"""

REJECTED_MESSAGE = """
❌ <b>Request #{request_id} — Rejected</b>

Unfortunately your request could not be processed.

<b>Reason:</b> {reason}

<b>What next?</b>
• Any reserved funds have been refunded to your wallet
• You can retry after reviewing the issue
• Contact support if you need help

<i>Tap "📞 Support" from the main menu to reach us.</i>
"""

CURRENT_RATE = """
💹 <b>Live Exchange Rates</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>
🇮🇳 <b>1 INR  =  {inr_to_npr} NPR</b>
🇳🇵 <b>1 NPR  =  {npr_to_inr} INR</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>

📌 Service fee: {fee}%
🕐 Rates updated by admin as needed.
"""

TRANSACTION_HISTORY = """
📜 <b>Transaction History</b>

{transactions}
<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>Completed:</b> {total} txn(s) · <b>Volume:</b> {total_amount}
"""

HOW_IT_WORKS = """
📚 <b>How It Works</b>

<b>1️⃣ Load Wallet</b>
Add INR or NPR funds via UPI / eSewa. Admin verifies and credits your wallet.

<b>2️⃣ Exchange</b>
Pick direction (INR→NPR or NPR→INR), enter amount, review the summary.

<b>3️⃣ Confirm &amp; Pay</b>
Send payment to the UPI / eSewa ID shown, take a screenshot.

<b>4️⃣ Upload Proof</b>
Send the screenshot + transaction ID in the bot.

<b>5️⃣ Admin Verifies</b>
Our team checks the proof — usually 5–15 minutes.

<b>6️⃣ Receive Funds</b>
Once approved, your wallet / destination account is credited instantly.

<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>
🔐 <i>All transactions are encrypted and manually verified for your security.</i>
"""

SUPPORT_MENU = """
📞 <b>Support Centre</b>

<b>❓ Common Questions</b>
• <b>How long does verification take?</b>
  5–15 minutes during business hours.
• <b>Why is there a service fee?</b>
  The {fee}% fee covers processing and operational costs.
• <b>What payment methods?</b>
  UPI (India) and eSewa (Nepal).
• <b>Is my money safe?</b>
  Yes — funds are held and only released after admin verification.

<b>💬 Still need help?</b>
Open a support ticket and we'll get back to you shortly.
"""

SUPPORT_TICKET_CREATED = """
🎟️ <b>Support Ticket #{ticket_id} Opened</b>

Your message has been sent to our support team.
We typically respond within 30 minutes.

You'll receive a notification here when we reply.
<i>You can send follow-up messages using the button below.</i>
"""

SUPPORT_TICKET_REPLY = """
📨 <b>Support Reply — Ticket #{ticket_id}</b>

{reply_text}

<i>Tap "Reply" below to respond.</i>
"""

SUPPORT_ADMIN_TICKET = """
🎟️ <b>Support Ticket #{ticket_id}</b>

<b>From:</b> <a href="tg://user?id={user_id}">@{username}</a> (<code>{user_id}</code>)
<b>Subject:</b> {subject}

<b>Message:</b>
{message_text}
"""

SUPPORT_TICKET_CLOSED = """
✅ <b>Ticket #{ticket_id} Closed</b>

Your support ticket has been resolved and closed by our team.

If you need further help, you can open a new ticket anytime.
<i>Thank you for using our support! 🙏</i>
"""

PROFILE_MESSAGE = """
👤 <b>Your Profile</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>Name:</b>     {first_name}
<b>Username:</b> @{username}
<b>ID:</b>       <code>{user_id}</code>
<b>Member since:</b> {joined_date}

<b>💼 Wallet</b>
• INR: <b>{wallet_inr}</b>
• NPR: <b>{wallet_npr}</b>

<b>📊 Stats</b>
• Exchanges completed: <b>{total_exchanges}</b>
• Total volume: <b>{total_amount}</b>

<b>🔗 Referral</b>
• Your code: <code>{referral_code}</code>
• Referral link: {referral_link}
• Friends referred: <b>{referred_count}</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>
"""

ADMIN_STATS = """
📊 <b>Bot Statistics</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>
<b>👥 Users</b>
• Total: {total_users}  |  New today: {new_users}
• Active today: {active_today}

<b>💱 Transactions</b>
• Total: {total_transactions}
• Completed: {completed}  |  Pending: {pending}  |  Rejected: {rejected}

<b>💰 Volume</b>
• INR volume: {total_inr}
• NPR volume: {total_npr}
• Fees collected: {total_fees}

<b>💹 Rates</b>
• INR→NPR: {inr_to_npr}  |  NPR→INR: {npr_to_inr}

<b>💬 Support</b>
• Open tickets: {open_tickets}
<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>
<i>Updated: {updated_at}</i>
"""

ERROR_MESSAGES = {
    "invalid_amount": "❌ Please enter a valid number between 100 and 1,00,000.",
    "amount_too_low": "❌ Minimum exchange amount is 100.",
    "amount_too_high": "❌ Maximum exchange amount is 1,00,000.",
    "anti_spam": "⏱️ Too many requests. Please wait {wait_time} minute(s) before trying again.",
    "banned": "🚫 Your account has been suspended. Tap Support to contact us.",
    "database_error": "⚠️ A database error occurred. Please try again later.",
    "invalid_input": "❌ Invalid input — please try again.",
}

SUCCESS_MESSAGES = {
    "payment_received": "✅ Payment proof received! Our team will verify shortly.",
    "exchange_completed": "🎉 Exchange completed successfully!",
}
