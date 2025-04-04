from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from pytrends.request import TrendReq
import matplotlib.pyplot as plt
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_SHEET_NAME = "Keyword Logs"
CREDENTIAL_FILE = "credentials.json"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIAL_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).sheet1

pytrends = TrendReq(hl='en-US', tz=360)

def plot_trends(data, keywords):
    plt.figure(figsize=(10, 5))
    for kw in keywords:
        plt.plot(data.index, data[kw], label=kw)
    plt.legend()
    plt.title("Google Trends - 7 ngày qua")
    plt.xlabel("Ngày")
    plt.ylabel("Độ quan tâm")
    plt.xticks(rotation=45)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

def log_to_sheet(user, keywords):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([now, user, ", ".join(keywords)])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Gửi từ khóa (tối đa 5, cách nhau bằng dấu phẩy) để tra Google Trends.\nGửi /trending để xem top từ khóa hot tại Việt Nam.")

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trending = pytrends.trending_searches(pn='vietnam')[0].tolist()[:10]
    msg = "*📈 Top từ khóa thịnh hành tại Việt Nam:*
\n"
    msg += '\n'.join([f"{i+1}. {kw}" for i, kw in enumerate(trending)])
    await update.message.reply_markdown(msg)

async def search_trends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keywords = update.message.text.strip().split(",")
    keywords = [kw.strip() for kw in keywords if kw.strip()]
    if len(keywords) > 5:
        await update.message.reply_text("⚠️ Chỉ nhập tối đa 5 từ khóa.")
        return
    try:
        pytrends.build_payload(keywords, cat=0, timeframe='now 7-d', geo='VN')
        data = pytrends.interest_over_time()
        if data.empty:
            await update.message.reply_text("❌ Không có dữ liệu.")
            return

        scores = {kw: data[kw].iloc[-1] for kw in keywords}
        msg = "*📊 So sánh từ khóa (7 ngày qua):*
\n"
        for kw, score in scores.items():
            msg += f"🔹 `{kw}`: {score}/100\n"
        await update.message.reply_markdown(msg)

        plot_buf = plot_trends(data, keywords)
        await update.message.reply_photo(photo=plot_buf, caption="📈 Biểu đồ xu hướng")

        log_to_sheet(update.effective_user.full_name, keywords)

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {str(e)}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_trends))
    print("🤖 Bot is running...")
    app.run_polling()
