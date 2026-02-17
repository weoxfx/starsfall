import os
import uuid
import asyncio
import requests

from fastapi import FastAPI, Request
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

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

# ==============================
# /start command
# ==============================
@dp.message(commands=["start"])
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
# CREATE INVOICE API (Lovable calls)
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
        provider_token="",  # IMPORTANT FOR STARS
    )

    return {"status": "invoice_sent"}


# ==============================
# PRE CHECKOUT (REQUIRED)
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

    # 🔔 notify your backend / lovable
    try:
        requests.post(
            f"{WEBAPP_URL}/payment-success",
            json={
                "user_id": user_id,
                "stars": stars_paid,
                "payload": payload,
            },
            timeout=10,
        )
    except Exception as e:
        print("Webhook error:", e)

    await message.answer("✅ Payment successful! Stars added.")


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
