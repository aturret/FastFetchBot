from core.models.telegram_chat import document_list as telegram_chat_document_list

# Only TelegramMessage document model for the bot's database
document_list = list(telegram_chat_document_list)
