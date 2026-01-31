import sqlite3
import time
import csv
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from openpyxl import Workbook

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

# ===== CONFIG =====
ADMIN_BOT_TOKEN = "7568976449:AAGkkUOQ0bQnFQFND304iqIGxCYAJpiVSUQ"
ADMIN_IDS = [8507414640]
DB = "bot_data.db"
START_TIME = time.time()
# ==================


# ---------- DB ----------
def get_db():
    return sqlite3.connect(DB)


# ---------- ADMIN CHECK ----------
def is_admin(uid):
    return uid in ADMIN_IDS


# ---------- UI PANEL ----------
ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["📊 Stats", "📅 Today", "📆 Week", "🗓 Month"],
        ["🧾 Orders", "📤 Export CSV", "📥 Export Excel"],
        ["📈 Graph", "📢 Broadcast"],
        ["💰 Edit Price"],
        ["💾 Backup DB", "⏱ Uptime"]
    ],
    resize_keyboard=True
)


# ---------- START ----------
async def start(update, context):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("❌ Not authorized")

    await update.message.reply_text(
        "🧠 Admin Dashboard Ready",
        reply_markup=ADMIN_KEYBOARD
    )


# ---------- USERS ----------
async def users(update, context):
    if not is_admin(update.effective_user.id):
        return

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    db.close()

    await update.message.reply_text(f"👥 Total users: {count}")


# ---------- STATS ----------
def get_stats(days=None):
    db = get_db()
    cur = db.cursor()

    if days:
        since = datetime.now() - timedelta(days=days)
        cur.execute("SELECT COUNT(*), SUM(amount) FROM orders WHERE time >= ?", (since,))
    else:
        cur.execute("SELECT COUNT(*), SUM(amount) FROM orders")

    count, total = cur.fetchone()
    db.close()

    return count or 0, total or 0


async def stats(update, context):
    if not is_admin(update.effective_user.id):
        return

    count, total = get_stats()
    await update.message.reply_text(f"📊 Total Stats\n\nOrders: {count}\nRevenue: ₹{total}")


async def todaystats(update, context):
    count, total = get_stats(1)
    await update.message.reply_text(f"📅 Today\nOrders: {count}\nRevenue: ₹{total}")


async def weekstats(update, context):
    count, total = get_stats(7)
    await update.message.reply_text(f"📆 This Week\nOrders: {count}\nRevenue: ₹{total}")


async def monthstats(update, context):
    count, total = get_stats(30)
    await update.message.reply_text(f"🗓 This Month\nOrders: {count}\nRevenue: ₹{total}")


# ---------- PRICE EDIT ----------
async def edit_price(update, context):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        "💰 Send like this:\n/setprice 500 20\n\nMeans:\nVoucher 500 = ₹20"
    )


async def setprice(update, context):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /setprice 500 20")

    try:
        voucher = int(context.args[0])
        price = int(context.args[1])
    except:
        return await update.message.reply_text("Numbers only")

    db = get_db()
    cur = db.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS prices (voucher INTEGER PRIMARY KEY, price INTEGER)")
    cur.execute("INSERT OR REPLACE INTO prices VALUES (?, ?)", (voucher, price))
    db.commit()
    db.close()

    await update.message.reply_text(f"✅ Price updated: ₹{voucher} = ₹{price}")


# ---------- EXPORT ----------
async def export_csv(update, context):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT oid, user, amount FROM orders")
    rows = cur.fetchall()
    db.close()

    with open("orders.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["OrderID", "User", "Amount"])
        writer.writerows(rows)

    await update.message.reply_document(open("orders.csv", "rb"))


async def export_excel(update, context):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT oid, user, amount FROM orders")
    rows = cur.fetchall()
    db.close()

    wb = Workbook()
    ws = wb.active
    ws.append(["OrderID", "User", "Amount"])
    for row in rows:
        ws.append(row)

    wb.save("orders.xlsx")
    await update.message.reply_document(open("orders.xlsx", "rb"))


# ---------- GRAPH ----------
async def graph(update, context):
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT DATE(time), SUM(amount)
        FROM orders
        GROUP BY DATE(time)
        ORDER BY DATE(time) DESC
        LIMIT 7
    """)
    data = cur.fetchall()
    db.close()

    if not data:
        return await update.message.reply_text("No data to plot.")

    dates = [d for d, _ in data][::-1]
    amounts = [a for _, a in data][::-1]

    plt.figure()
    plt.plot(dates, amounts, marker="o")
    plt.title("Last 7 Days Revenue")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("graph.png")
    plt.close()

    await update.message.reply_photo(open("graph.png", "rb"))


# ---------- BACKUP ----------
async def backup(update, context):
    await update.message.reply_document(open(DB, "rb"))


# ---------- BROADCAST ----------
async def broadcast(update, context):
    if not context.args:
        return await update.message.reply_text("Use:\n/broadcast your message")

    msg = " ".join(context.args)

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM users")
    users = cur.fetchall()
    db.close()

    sent = 0
    for (uid,) in users:
        try:
            await context.bot.send_message(uid, msg)
            sent += 1
        except:
            pass

    await update.message.reply_text(f"📢 Sent to {sent} users")


# ---------- UPTIME ----------
async def uptime(update, context):
    seconds = int(time.time() - START_TIME)
    await update.message.reply_text(f"⏱ Uptime: {seconds}s")


# ---------- BUTTON HANDLER ----------
async def button_handler(update, context):
    t = update.message.text

    if t == "📊 Stats": return await stats(update, context)
    if t == "📅 Today": return await todaystats(update, context)
    if t == "📆 Week": return await weekstats(update, context)
    if t == "🗓 Month": return await monthstats(update, context)
    if t == "📤 Export CSV": return await export_csv(update, context)
    if t == "📥 Export Excel": return await export_excel(update, context)
    if t == "📈 Graph": return await graph(update, context)
    if t == "💾 Backup DB": return await backup(update, context)
    if t == "⏱ Uptime": return await uptime(update, context)
    if t == "📢 Broadcast": return await update.message.reply_text("Use /broadcast text")
    if t == "💰 Edit Price": return await edit_price(update, context)


# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("setprice", setprice))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))

    print("Admin bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()