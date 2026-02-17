import os
import uuid
import asyncio
import requests
from aiogram.filters import Command
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    LabeledPrice,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
PAYMENT_WEBHOOK_URL = os.getenv("PAYMENT_WEBHOOK_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
ADMIN_ID = 6186511950

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

# ==============================
# CORS — allows browser requests
# ==============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Headers required by Supabase edge functions
def get_supabase_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "apikey": SUPABASE_ANON_KEY,
    }

# ==============================
# /start command
# ==============================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Open StarsFall",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]
        ]
    )
    await message.answer(
        "✨ Welcome to StarsFall!\n\nPlay and unlock premium rewards ⭐",
        reply_markup=kb,
    )


# ==============================
# CREATE INVOICE LINK (returns link for in-app popup)
# ==============================
@app.post("/create-invoice-link")
async def create_invoice_link(request: Request):
    data = await request.json()

    user_id = data.get("user_id")
    stars = data.get("stars")

    if not user_id or not stars:
        return {"status": "error", "message": "Missing data"}

    payload = f"stars_{uuid.uuid4()}"
    prices = [LabeledPrice(label="Stars Pack", amount=int(stars))]

    # Creates a link instead of sending a message
    link = await bot.create_invoice_link(
        title="⭐ Stars Purchase",
        description=f"Buy {stars} Stars for StarsFall",
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token="",
    )

    return {"status": "ok", "link": link}


# ==============================
# CREATE INVOICE API (fallback — sends message)
# ==============================
@app.post("/create-stars-invoice")
async def create_invoice(request: Request):
    data = await request.json()

    user_id = data.get("user_id")
    stars = data.get("stars")

    if not user_id or not stars:
        return {"status": "error", "message": "Missing data"}

    payload = f"stars_{uuid.uuid4()}"
    prices = [LabeledPrice(label="Stars Pack", amount=int(stars))]

    await bot.send_invoice(
        chat_id=int(user_id),
        title="⭐ Stars Purchase",
        description=f"Buy {stars} Stars",
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token="",
    )

    return {"status": "invoice_sent"}


# ==============================
# PRE CHECKOUT (REQUIRED by Telegram)
# ==============================
@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


# ==============================
# SUCCESSFUL PAYMENT
# ==============================
@dp.message(lambda m: m.successful_payment)
async def successful_payment(message: types.Message):
    payment = message.successful_payment
    user_id = message.from_user.id
    stars_paid = payment.total_amount
    payload = payment.invoice_payload

    webhook_url = PAYMENT_WEBHOOK_URL or f"{WEBAPP_URL}/payment-success"
    try:
        r = requests.post(
            webhook_url,
            json={
                "user_id": user_id,
                "stars": stars_paid,
                "payload": payload,
            },
            headers=get_supabase_headers(),
            timeout=10,
        )
        print(f"Webhook status: {r.status_code} | Response: {r.text}")
    except Exception as e:
        print(f"Webhook error: {e}")

    await message.answer("✅ Payment successful! Stars added to your balance.")


# ==============================
# ADMIN: Test the payment webhook
# ==============================
@dp.message(Command("testapi"))
async def test_api_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ You are not authorized.")
        return

    await message.answer("🧪 Testing payment webhook...")

    webhook_url = PAYMENT_WEBHOOK_URL or f"{WEBAPP_URL}/payment-success"
    try:
        r = requests.post(
            webhook_url,
            json={
                "user_id": message.from_user.id,
                "stars": 10,
                "payload": "TEST_PAYLOAD",
                "test": True,
            },
            headers=get_supabase_headers(),
            timeout=10,
        )
        await message.answer(
            f"✅ Webhook Response: {r.status_code}\n{r.text}"
        )
    except Exception as e:
        await message.answer(f"❌ Webhook Failed:\n{e}")


# ==============================
# RUN BOT IN BACKGROUND
# ==============================
async def start_bot():
    await dp.start_polling(bot)


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(start_bot())


# ==============================
# HEALTH CHECK
# ==============================
@app.get("/")
async def root():
    return {"status": "StarsFall bot running"}
