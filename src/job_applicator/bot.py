from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from .config import load_config
import logging
import random
import string

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
config = load_config()
bot = Bot(token=config.get("telegram_token"))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# States
class Form(StatesGroup):
    email = State()
    otp = State()

# Helper function to generate OTP
def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

# Command /start
@dp.message_handler(commands=['start'], state='*')
async def send_welcome(message: types.Message):
    await Form.email.set()
    await message.reply("Привіт! Будь ласка, введіть ваш email:")

# Process email
@dp.message_handler(state=Form.email)
async def process_email(message: types.Message, state: FSMContext):
    email = message.text
    if email in config.trusted_emails:
        otp = generate_otp()
        # Here you should send OTP to the email
        await message.reply(f"Ваш OTP: {otp}")
        await state.update_data(email=email, otp=otp)
        await Form.otp.set()
    else:
        await message.reply("Ви не в довіреному списку. Будь ласка, спробуйте знову.")
        await state.finish()

# Process OTP
@dp.message_handler(state=Form.otp)
async def process_otp(message: types.Message, state: FSMContext):
    otp = message.text
    user_data = await state.get_data()
    if otp == user_data['otp']:
        await message.reply("Ви успішно авторизовані!")
        # Here you can unlock features
    else:
        await message.reply("Неправильний OTP. Будь ласка, спробуйте знову.")
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
