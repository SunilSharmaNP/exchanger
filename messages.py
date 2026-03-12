# Professional message templates with emojis

WELCOME_MESSAGE = """
🌍 <b>Welcome to Currency Exchange Bot</b>

Your trusted platform for seamless INR ⇄ NPR currency exchange.

<b>✨ Key Features:</b>
• 🔄 Instant exchange calculation
• 💯 Transparent pricing with clear fees
• 🔐 Secure payment verification
• ⚡ Fast payout system
• 📊 Complete transaction history
• 💬 24/7 Support

<b>📌 How to get started:</b>
1. Select exchange direction
2. Enter amount
3. Verify your payment
4. Get instant payout

<i>All transactions are secure and verified by our admin team.</i>
"""

EXCHANGE_STARTED = """
💱 <b>Select Exchange Type</b>

Choose which currency you want to exchange:

• <b>INR → NPR:</b> Convert Indian Rupees to Nepali Rupees
• <b>NPR → INR:</b> Convert Nepali Rupees to Indian Rupees

Click below to continue!
"""

ENTER_AMOUNT = """
💰 <b>Enter Exchange Amount</b>

Please enter the amount you want to exchange:

<b>⚠️ Limits:</b>
• Minimum: 100
• Maximum: 100,000

<i>Send me the amount as a number (e.g., 1000)</i>
"""

EXCHANGE_SUMMARY = """
📊 <b>Exchange Summary</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>

You are exchanging: <b>{amount} {from_currency}</b>

Exchange rate: <b>1 {from_currency} = {rate} {to_currency}</b>

Amount to receive: <b>{calculated_amount} {to_currency}</b>

Service fee ({fee_percent}%): <b>- {service_fee} {to_currency}</b>

<b>Final amount:</b> <b>{final_amount} {to_currency}</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>

<i>Please review the details and confirm to proceed with payment.</i>
"""

PAYMENT_INSTRUCTIONS = """
💳 <b>Payment Instructions</b>

Send payment using one of the methods below:

<b>Method 1: UPI</b>
UPI ID: <code>{upi_id}</code>

<b>Method 2: eSewa (Nepal)</b>
eSewa ID: <code>{esewa_id}</code>

<b>⚠️ Important Notes:</b>
• Include your User ID in payment reference: <code>{user_id}</code>
• Screenshot your payment confirmation
• Click "I Have Paid" button after sending payment
• Support team will verify and process within 5 minutes

<i>Once payment is verified, you'll receive your amount instantly!</i>
"""

PAYMENT_VERIFICATION = """
✅ <b>Payment Verification</b>

Please provide the following details for verification:

<b>Step 1:</b> Upload payment screenshot
<b>Step 2:</b> Send transaction ID

<i>Make sure the screenshot clearly shows the transaction details.</i>
"""

ADMIN_REQUEST = """
🔔 <b>New Exchange Request</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>User Details:</b>
• User ID: <code>{user_id}</code>
• Username: @{username}

<b>Exchange Details:</b>
• Type: {exchange_type}
• Amount: {amount}
• Rate: {rate}
• Final Amount: {final_amount} {to_currency}

<b>Payment Proof:</b>
• Transaction ID: <code>{transaction_id}</code>
• Screenshot: ✅ Attached

<code>━━━━━━━━━━━━━━━━━━━━━━━━━</code>

<i>Click below to approve or reject this request.</i>
"""

APPROVED_MESSAGE = """
✅ <b>Exchange Approved!</b>

Great news! Your exchange request has been approved by our admin.

<b>Details:</b>
• Amount: {final_amount} {to_currency}
• Status: ⏳ Processing Payout
• Estimated Time: 5-10 minutes

<i>You'll receive a confirmation message once the payout is completed.</i>
"""

COMPLETED_MESSAGE = """
✨ <b>Transaction Completed!</b>

Your exchange has been successfully processed.

<b>Final Details:</b>
• Sent: {sent_amount} {from_currency}
• Received: {received_amount} {to_currency}
• Fee Charged: {service_fee} {to_currency}
• Transaction ID: <code>{request_id}</code>
• Completed at: {timestamp}

<b>Balance Update:</b>
• {to_currency} Wallet: +{received_amount}

<i>Thank you for using our service! Your money should arrive shortly.</i>
"""

REJECTED_MESSAGE = """
❌ <b>Exchange Rejected</b>

Unfortunately, your exchange request could not be processed.

<b>Reason:</b> {reason}

<b>Please Note:</b>
• Your payment will be refunded
• You can retry the exchange after reviewing the requirements
• Contact support if you have questions

<i>We're here to help! Reach out to our support team for assistance.</i>
"""

CURRENT_RATE = """
💹 <b>Current Exchange Rates</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━</code>

💵 <b>INR to NPR</b>
1 INR = <b>{inr_to_npr} NPR</b>

₨ <b>NPR to INR</b>
1 NPR = <b>{npr_to_inr} INR</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━</code>

<i>Rates are updated every 24 hours. Service fee: 2.5%</i>
"""

TRANSACTION_HISTORY = """
📜 <b>Your Transaction History</b>

{transactions}

<code>━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>Summary:</b>
• Total Transactions: {total}
• Total Amount Exchanged: {total_amount}

<i>Tap on any transaction for detailed information.</i>
"""

HOW_IT_WORKS = """
📚 <b>How It Works</b>

<b>Step 1️⃣ - Select Exchange Type</b>
Choose whether you want to exchange INR to NPR or NPR to INR.

<b>Step 2️⃣ - Enter Amount</b>
Tell us how much you want to exchange. Our bot will calculate instantly!

<b>Step 3️⃣ - Review Summary</b>
Check the exchange rate, fee, and final amount. Everything is transparent!

<b>Step 4️⃣ - Send Payment</b>
We provide UPI and eSewa payment methods. Send payment using your preferred method.

<b>Step 5️⃣ - Verify Payment</b>
Upload your payment screenshot and transaction ID for verification.

<b>Step 6️⃣ - Admin Approval</b>
Our team verifies your payment within 5 minutes.

<b>Step 7️⃣ - Receive Money</b>
Once approved, payout instructions are automatically sent!

🔐 <i>Your security is our priority. All transactions are encrypted and verified.</i>
"""

SUPPORT_MESSAGE = """
📞 <b>Support & Help</b>

<b>❓ Common Questions:</b>
• <b>Why is there a service fee?</b> The 2.5% fee covers transaction costs and operational expenses.
• <b>How long does verification take?</b> Usually 5-10 minutes during business hours.
• <b>What payment methods do you accept?</b> UPI and eSewa (Nepal).
• <b>Is my transaction secure?</b> Yes! All payments are verified by our admin team.

<b>📧 Contact Us:</b>
• WhatsApp: wa.me/+977XXXXXXXXX
• Email: support@exchangebot.com
• Telegram: @support_bot

<i>We're available 24/7 to help you!</i>
"""

PROFILE_MESSAGE = """
👤 <b>Your Profile</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>Account Info:</b>
• Name: {first_name}
• Username: @{username}
• User ID: <code>{user_id}</code>
• Member Since: {joined_date}

<b>Wallet Balance:</b>
• 💵 INR: {wallet_inr}
• ₨ NPR: {wallet_npr}

<b>Exchange Statistics:</b>
• Total Exchanges: {total_exchanges}
• Total Amount: {total_amount}

<b>Referral:</b>
• Your Code: <code>{referral_code}</code>
• People Referred: {referred_count}

<code>━━━━━━━━━━━━━━━━━━━━━━━</code>
"""

ADMIN_STATS = """
📊 <b>Bot Statistics</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>User Stats:</b>
• Total Users: {total_users}
• Active Users (Today): {active_today}
• New Users (Today): {new_users}

<b>Transaction Stats:</b>
• Total Transactions: {total_transactions}
• Completed: {completed}
• Pending: {pending}
• Rejected: {rejected}

<b>Volume Stats:</b>
• Total Volume (INR): {total_inr}
• Total Volume (NPR): {total_npr}
• Total Fees Collected: {total_fees}

<b>Exchange Rates:</b>
• INR → NPR: {inr_to_npr}
• NPR → INR: {npr_to_inr}

<code>━━━━━━━━━━━━━━━━━━━━━━━</code>
<i>Last updated: {updated_at}</i>
"""

ERROR_MESSAGES = {
    "invalid_amount": "❌ Invalid amount! Please enter a number between 100 and 100,000.",
    "amount_too_low": "❌ Amount is too low! Minimum exchange is 100.",
    "amount_too_high": "❌ Amount is too high! Maximum exchange is 100,000.",
    "anti_spam": "⏱️ Please wait before making another exchange. You can make another in {wait_time} minutes.",
    "banned": "🚫 Your account has been suspended. Contact support for details.",
    "database_error": "⚠️ Database error. Please try again later.",
    "invalid_input": "❌ Invalid input! Please try again.",
}

SUCCESS_MESSAGES = {
    "payment_received": "✅ Payment verification received! Admin will review shortly.",
    "exchange_completed": "✨ Exchange completed successfully!",
}
