import uuid, sqlite3, random
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# ================= CONFIG =================
BOT_TOKEN = "8328538969:AAH4oE7_c5IpJdmtLhtXVcxxYGUnOoELuyM"
FORCE_CHANNEL = "@SheinBotUpdates"
LOG_CHANNEL = "@SheinBotUpdates"
SUPPORT_BOT = "@SheinServiceSupportBot"
ADMIN_IDS = [8507414640]

QR_IMAGE = "payment_qr.jpg"
COMPLAINT_IMAGE = "complaint.jpg"
# =========================================

# ================= DB =================
db = sqlite3.connect("bot_data.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    ref_by INTEGER,
    referrals INTEGER DEFAULT 0
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS orders (
    oid TEXT,
    user INTEGER,
    voucher INTEGER,
    qty INTEGER,
    unit_price INTEGER,
    total INTEGER,
    status TEXT,
    time TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS prices (
    voucher INTEGER PRIMARY KEY,
    price INTEGER
)""")

db.commit()

# ================= DATA =================
DEFAULT_PRICES = {500: 15, 1000: 25, 2000: 50, 4000: 150}
MIN_QTY = {500: 5, 1000: 2, 2000: 2, 4000: 1}

STOCK_ORIGINAL = {500: 200, 1000: 150, 2000: 100, 4000: 50}
stock = STOCK_ORIGINAL.copy()

user_state = {}

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🛒 Buy", "📦 Stock"],
        ["👤 Profile", "🎁 Referral"],
        ["📦 My Orders", "🆘 Support"]
    ],
    resize_keyboard=True
)

# ================= HELPERS =================
def get_price(voucher):
    cur.execute("SELECT price FROM prices WHERE voucher = ?", (voucher,))
    row = cur.fetchone()
    return row[0] if row else DEFAULT_PRICES[voucher]

def auto_stock_control(voucher, qty):
    stock[voucher] -= qty
    if stock[voucher] <= 5:
        stock[voucher] = STOCK_ORIGINAL[voucher]

def stock_text():
    return (
        f"📦 <b>Live Stock</b>\n\n"
        f"🎫 ₹500 → {stock[500]}\n"
        f"🎫 ₹1000 → {stock[1000]}\n"
        f"🎫 ₹2000 → {stock[2000]}\n"
        f"🎫 ₹4000 → {stock[4000]}\n\n"
        "⚡ Auto restock enabled"
    )

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cur.execute("INSERT OR IGNORE INTO users(id) VALUES (?)", (uid,))
    db.commit()

    try:
        m = await context.bot.get_chat_member(FORCE_CHANNEL, uid)
        if m.status not in ["member", "administrator", "creator"]:
            raise Exception()
    except:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL[1:]}")],
            [InlineKeyboardButton("✅ I Joined", callback_data="check_join")]
        ])
        return await update.message.reply_text(
            "🔒 <b>Join our channel first to continue</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )

    price_text = (
        f"\n\n<b>💳 Voucher Price List</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎫 ₹500 → ₹{get_price(500)} each\n"
        f"🎫 ₹1000 → ₹{get_price(1000)} each\n"
        f"🎫 ₹2000 → ₹{get_price(2000)} each\n"
        f"🎫 ₹4000 → ₹{get_price(4000)} each\n"
    )

    await update.message.reply_text(
        "✨ <b>Welcome to Premium Voucher Store</b>\n\n"
        "🎁 Genuine vouchers\n"
        "📸 Manual verification\n"
        "🛡 Human approval system\n\n"
        + price_text +
        "\n👇 Use menu below to continue",
        reply_markup=MAIN_MENU,
        parse_mode="HTML"
    )

# ================= CALLBACKS =================
async def buttons(update, context):
    q = update.callback_query
    await q.answer()

    if q.data == "check_join":
        return await start(update, context)

    if q.data.startswith("buy_"):
        val = int(q.data.split("_")[1])
        user_state[q.from_user.id] = val
        price = get_price(val)

        return await q.message.reply_text(
            f"🎫 <b>₹{val} Voucher Selected</b>\n\n"
            f"💵 Price per voucher: ₹{price}\n"
            f"📦 Minimum Quantity: {MIN_QTY[val]}\n\n"
            f"✍️ Now send quantity:",
            parse_mode="HTML"
        )

    if q.data.startswith("paid_"):
        oid = q.data.split("_")[1]

        cur.execute("SELECT voucher, qty, unit_price, total, user FROM orders WHERE oid=?", (oid,))
        row = cur.fetchone()
        if not row:
            return await q.answer("Order expired", show_alert=True)

        voucher, qty, price, total, user_id = row

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{oid}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{oid}")
            ]
        ])

        caption = (
            f"🧾 <b>New Payment Request</b>\n\n"
            f"🆔 Order: <code>{oid}</code>\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"🎫 Voucher: ₹{voucher}\n"
            f"📦 Qty: {qty}\n"
            f"💵 Unit: ₹{price}\n"
            f"💰 Total: ₹{total}"
        )

        await context.bot.send_message(
            LOG_CHANNEL,
            caption,
            parse_mode="HTML",
            reply_markup=kb
        )

        return await q.message.reply_text(
            "✅ <b>Payment received successfully</b>\n\n"
            "⏳ Your order is under admin verification\n"
            f"📩 Support: {SUPPORT_BOT}",
            parse_mode="HTML"
        )

    if q.data.startswith("approve_") or q.data.startswith("reject_"):
        if q.from_user.id not in ADMIN_IDS:
            return await q.answer("Not authorized", show_alert=True)

        action, oid = q.data.split("_")
        status = "APPROVED" if action == "approve" else "REJECTED"

        cur.execute("UPDATE orders SET status=? WHERE oid=?", (status, oid))
        db.commit()

        cur.execute("SELECT user FROM orders WHERE oid=?", (oid,))
        uid = cur.fetchone()[0]

        await context.bot.send_message(
            uid,
            f"📦 Order <code>{oid}</code>\nStatus: <b>{status}</b>",
            parse_mode="HTML"
        )

        await q.edit_message_text(
            q.message.text + f"\n\n<b>Status: {status}</b>",
            parse_mode="HTML"
        )

# ================= TEXT =================
async def handle_text(update, context):
    uid = update.effective_user.id
    txt = update.message.text

    if txt == "🛒 Buy":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"₹500 • ₹{get_price(500)}", callback_data="buy_500")],
            [InlineKeyboardButton(f"₹1000 • ₹{get_price(1000)}", callback_data="buy_1000")],
            [InlineKeyboardButton(f"₹2000 • ₹{get_price(2000)}", callback_data="buy_2000")],
            [InlineKeyboardButton(f"₹4000 • ₹{get_price(4000)}", callback_data="buy_4000")]
        ])
        return await update.message.reply_text(
            "🛒 <b>Select your voucher below</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )

    if txt == "📦 Stock":
        return await update.message.reply_text(stock_text(), parse_mode="HTML")

    if txt == "🆘 Support":
        return await update.message.reply_photo(
            open(COMPLAINT_IMAGE, "rb"),
            caption=f"🆘 Need help?\nContact: {SUPPORT_BOT}"
        )

    if txt == "🎁 Referral":
        return await referral(update, context)

    if txt == "📦 My Orders":
        return await myorders(update, context)

    if txt == "👤 Profile":
        return await profile(update, context)

    if uid not in user_state:
        return

    if not txt.isdigit():
        return await update.message.reply_text("Send numbers only.")

    qty = int(txt)
    voucher = user_state[uid]

    if qty < MIN_QTY[voucher]:
        return await update.message.reply_text(f"Minimum is {MIN_QTY[voucher]}")

    unit = get_price(voucher)
    total = qty * unit
    oid = str(uuid.uuid4())[:8].upper()

    auto_stock_control(voucher, qty)

    cur.execute(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (oid, uid, voucher, qty, unit, total, "PENDING", datetime.now().isoformat())
    )
    db.commit()

    await update.message.reply_photo(
        open(QR_IMAGE, "rb"),
        caption=(
            f"🧾 <b>Order Created</b>\n\n"
            f"🆔 ID: <code>{oid}</code>\n"
            f"🎫 Voucher: ₹{voucher}\n"
            f"📦 Qty: {qty}\n"
            f"💵 Unit Price: ₹{unit}\n"
            f"💰 Payable Amount: ₹{total}\n\n"
            "📸 Please send payment screenshot"
        ),
        parse_mode="HTML"
    )

    del user_state[uid]

# ================= PHOTO =================
async def handle_photo(update, context):
    uid = update.message.from_user.id
    cur.execute("SELECT oid FROM orders WHERE user=? ORDER BY time DESC LIMIT 1", (uid,))
    row = cur.fetchone()

    if not row:
        return await update.message.reply_text("No active order.")

    oid = row[0]

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I Have Paid", callback_data=f"paid_{oid}")]
    ])

    await update.message.reply_text(
        "📨 Screenshot received.\nTap below to submit for verification.",
        reply_markup=kb
    )

# ================= EXTRA =================
async def myorders(update, context):
    uid = update.effective_user.id
    cur.execute("SELECT oid, total, status FROM orders WHERE user=?", (uid,))
    rows = cur.fetchall()

    if not rows:
        return await update.message.reply_text("No orders yet.")

    text = "📦 Your Orders:\n\n"
    for oid, amt, status in rows:
        text += f"{oid} → ₹{amt} → {status}\n"

    await update.message.reply_text(text)

async def profile(update, context):
    uid = update.effective_user.id
    cur.execute("SELECT COUNT(*), SUM(total) FROM orders WHERE user=?", (uid,))
    count, spent = cur.fetchone()

    await update.message.reply_text(
        f"👤 Profile\n\n"
        f"🆔 {uid}\n"
        f"📦 Orders: {count}\n"
        f"💰 Spent: ₹{spent or 0}"
    )

async def referral(update, context):
    uid = update.effective_user.id
    cur.execute("SELECT referrals FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
    count = row[0] if row else 0

    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={uid}"

    await update.message.reply_text(
        f"🎁 Refer & Earn\n\n"
        f"Invite friends & get FREE ₹4000 voucher 🎉\n"
        f"Target: 15 referrals\n\n"
        f"🔗 Your link:\n{link}\n\n"
        f"👥 Referrals: {count}/15\n\n"
        "🏆 Leaderboard: /topreferrals"
    )

async def topreferrals(update, context):
    cur.execute("SELECT id, referrals FROM users ORDER BY referrals DESC LIMIT 10")
    rows = cur.fetchall()

    if not rows:
        return await update.message.reply_text("No data yet.")

    text = "🏆 Top Referrers\n\n"
    rank = 1
    for uid, c in rows:
        text += f"{rank}. {uid} → {c}\n"
        rank += 1

    await update.message.reply_text(text)

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("topreferrals", topreferrals))

    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()