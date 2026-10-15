
import logging
import os

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smart_task_assistant.telegram")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

API_URL = os.getenv(
    "TELEGRAM_API_URL",
    "http://127.0.0.1:8000/chat",
).strip().rstrip("/")

API_BASE_URL = API_URL.rsplit("/", 1)[0]

TELEGRAM_INTERNAL_TOKEN = os.getenv(
    "TELEGRAM_INTERNAL_TOKEN",
    "",
).strip()


def internal_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TELEGRAM_INTERNAL_TOKEN}",
    }


def is_private_chat(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.type == ChatType.PRIVATE


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not is_private_chat(update):
        await update.effective_message.reply_text(
            "من فضلك استخدمي البوت في محادثة خاصة."
        )
        return

    user = update.effective_user
    message_obj = update.effective_message

    if user is None or message_obj is None:
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/telegram/resolve",
                headers=internal_headers(),
                json={"telegram_user_id": user.id},
            )

        if response.status_code == 200:
            await message_obj.reply_text(
                "أهلًا بيكي في Smart Task Assistant! 👋\n\n"
                "✅ حسابك مربوط بالفعل بموظف في الشركة.\n"
                "تقدري تستخدمي البوت مباشرةً من غير كود تفعيل.\n\n"
                "الأوامر المتاحة:\n"
                "/start - بدء الاستخدام\n"
                "/myid - معرفة رقم حساب Telegram\n"
                "/help - عرض المساعدة\n\n"
                "ابعتي طلبك بالعربية لتسجيل مهمة أو عرض مهامك "
                "أو السؤال عن سياسة الشركة."
            )
            return

        if response.status_code == 404:
            await message_obj.reply_text(
                "أهلًا بيكي في Smart Task Assistant! 👋\n\n"
                "حسابك لسه مش مربوط بموظف في الشركة.\n"
                "اطلبي كود التفعيل من مسؤول النظام، ثم اكتبي:\n"
                "/link CODE\n\n"
                "الأوامر المتاحة:\n"
                "/start - بدء الاستخدام\n"
                "/link CODE - ربط الحساب\n"
                "/myid - معرفة رقم حساب Telegram\n"
                "/help - عرض المساعدة"
            )
            return

        response.raise_for_status()

    except (httpx.RequestError, httpx.HTTPStatusError):
        logger.exception("Could not verify Telegram account link")
        await message_obj.reply_text(
            "مش قادر أتحقق من ربط حسابك حاليًا. "
            "حاولي مرة أخرى بعد قليل."
        )


async def my_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not is_private_chat(update):
        await update.effective_message.reply_text(
            "من فضلك استخدمي الأمر في محادثة خاصة."
        )
        return

    user = update.effective_user

    if user is None:
        return

    await update.effective_message.reply_text(
        f"رقم حساب Telegram الخاص بك هو:\n{user.id}\n\n"
        "يمكنك إعطاء الرقم لمسؤول النظام إذا طلبه منك."
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not is_private_chat(update):
        await update.effective_message.reply_text(
            "من فضلك استخدمي البوت في محادثة خاصة."
        )
        return

    await update.effective_message.reply_text(
        "لبدء الاستخدام:\n"
        "1. اطلبي كود التفعيل من مسؤول النظام.\n"
        "2. اكتبي /link CODE لربط حسابك.\n"
        "3. بعد نجاح الربط، ابعتي طلبك بالعربية.\n\n"
        "أمثلة:\n"
        "• سجل مهمة لي بكرة الساعة 10 أراجع التقرير\n"
        "• وش مهامي؟\n"
        "• كم يوم لازم أقدم قبل الإجازة؟\n\n"
        "الأوامر:\n"
        "/start - بدء الاستخدام\n"
        "/link CODE - ربط الحساب\n"
        "/myid - معرفة رقم حساب Telegram\n"
        "/help - عرض المساعدة"
    )


async def link_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not is_private_chat(update):
        await update.effective_message.reply_text(
            "من فضلك استخدمي الأمر في محادثة خاصة."
        )
        return

    user = update.effective_user
    message_obj = update.effective_message

    if user is None or message_obj is None:
        return

    if not context.args or len(context.args) != 1:
        await message_obj.reply_text(
            "طريقة الاستخدام:\n"
            "/link CODE\n\n"
            "استبدلي CODE بكود التفعيل الذي حصلتِ عليه "
            "من مسؤول النظام."
        )
        return

    code = context.args[0].strip()

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/telegram/link",
                headers=internal_headers(),
                json={
                    "telegram_user_id": user.id,
                    "code": code,
                },
            )

        if response.status_code == 400:
            await message_obj.reply_text(
                "كود التفعيل غير صالح أو انتهت صلاحيته. "
                "اطلبي كودًا جديدًا من مسؤول النظام."
            )
            return

        if response.status_code == 409:
            await message_obj.reply_text(
                "حساب Telegram أو الموظف مرتبط بالفعل بحساب آخر. "
                "تواصلي مع مسؤول النظام للمساعدة."
            )
            return

        response.raise_for_status()
        data = response.json()

        await message_obj.reply_text(
            data.get(
                "reply",
                "تم ربط حساب Telegram بنجاح.",
            )
        )

    except httpx.TimeoutException:
        logger.warning("Telegram link request timed out")
        await message_obj.reply_text(
            "استغرق الطلب وقتًا طويلًا. حاولي مرة أخرى."
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Telegram link API returned HTTP %s",
            exc.response.status_code,
        )
        await message_obj.reply_text(
            "تعذر إكمال الربط حاليًا. "
            "تأكدي من تشغيل التطبيق وتواصلي مع مسؤول النظام إذا استمرت المشكلة."
        )

    except httpx.RequestError:
        logger.exception("Could not connect to the link API")
        await message_obj.reply_text(
            "مش قادر أوصل للتطبيق حاليًا. "
            "تأكدي إن الـ API شغال."
        )

    except (ValueError, TypeError):
        logger.exception("Invalid Telegram link API response")
        await message_obj.reply_text(
            "حصل خطأ أثناء قراءة نتيجة الربط."
        )


async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not is_private_chat(update):
        await update.effective_message.reply_text(
            "من فضلك استخدمي البوت في محادثة خاصة."
        )
        return

    user = update.effective_user
    message_obj = update.effective_message

    if user is None or message_obj is None:
        return

    message = (message_obj.text or "").strip()

    if not message:
        await message_obj.reply_text(
            "اكتبي رسالة نصية من فضلك."
        )
        return

    if len(message) > 4000:
        await message_obj.reply_text(
            "الرسالة طويلة جدًا. اختصريها إلى 4000 حرف أو أقل."
        )
        return

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Resolve the employee using the Telegram account link.
            resolve_response = await client.post(
                f"{API_BASE_URL}/telegram/resolve",
                headers=internal_headers(),
                json={"telegram_user_id": user.id},
            )

            if resolve_response.status_code == 404:
                await message_obj.reply_text(
                    "حسابك لسه مش مربوط بموظف في الشركة.\n"
                    "اطلبي كود التفعيل من مسؤول النظام، "
                    "ثم اكتبي /link CODE."
                )
                return

            resolve_response.raise_for_status()
            resolved = resolve_response.json()
            employee_id = resolved.get("employee_id")

            if (
                not isinstance(employee_id, int)
                or isinstance(employee_id, bool)
            ):
                raise ValueError(
                    "Invalid employee ID returned by the API"
                )

            # Send the message using the resolved employee ID.
            response = await client.post(
                API_URL,
                json={
                    "user_id": employee_id,
                    "message": message,
                },
            )

        response.raise_for_status()
        data = response.json()
        reply = data.get("reply")

        if not isinstance(reply, str) or not reply.strip():
            await message_obj.reply_text(
                "وصل رد غير متوقع من التطبيق. حاولي مرة أخرى."
            )
            return

        # Keep individual Telegram messages within a safe length.
        remaining = reply.strip()

        while remaining:
            if len(remaining) <= 3900:
                part = remaining
                remaining = ""
            else:
                cut = remaining.rfind("\n", 0, 3900)

                if cut < 1000:
                    cut = 3900

                part = remaining[:cut]
                remaining = remaining[cut:].lstrip("\n")

            await message_obj.reply_text(part)

    except httpx.TimeoutException:
        logger.warning("The chat API timed out")
        await message_obj.reply_text(
            "التطبيق استغرق وقتًا طويلًا في الرد. حاولي مرة أخرى."
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "The API returned HTTP %s",
            exc.response.status_code,
        )
        await message_obj.reply_text(
            "التطبيق رجّع خطأ أثناء معالجة الطلب. حاولي مرة أخرى."
        )

    except httpx.RequestError:
        logger.exception("Could not connect to the API")
        await message_obj.reply_text(
            "مش قادر أوصل للتطبيق حاليًا. "
            "تأكدي إن الـ API شغال."
        )

    except (ValueError, TypeError):
        logger.exception("The API returned an invalid response")
        await message_obj.reply_text(
            "حصل خطأ في قراءة رد التطبيق."
        )


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "Missing TELEGRAM_BOT_TOKEN. Set it in .env."
        )

    if not TELEGRAM_INTERNAL_TOKEN:
        raise SystemExit(
            "Missing TELEGRAM_INTERNAL_TOKEN. Set it in .env."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myid", my_id))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("link", link_command))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text,
        )
    )

    logger.info("Starting Smart Task Assistant Telegram bot")
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
