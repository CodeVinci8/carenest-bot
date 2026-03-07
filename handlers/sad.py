import os
import random

from aiogram import Router, F
from aiogram.types import Message, FSInputFile

from filters.allowed_users import AllowedUserFilter

router = Router()


@router.message(F.text.lower() == "мне грустно 🥺", AllowedUserFilter())
async def sad_handler(message: Message):
    photos = [
        file_name for file_name in os.listdir("cute_photos")
        if file_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]

    if not photos:
        await message.answer("папка с милыми фото пока пустая 💔")
        return

    random_photo = random.choice(photos)
    photo_path = f"cute_photos/{random_photo}"

    photo = FSInputFile(photo_path)

    await message.answer_photo(
        photo=photo,
        caption="не грусти , я всегда рядом ❤️"
    )