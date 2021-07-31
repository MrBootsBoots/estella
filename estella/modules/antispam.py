from typing import List
import json
import requests

from telegram import Update, Bot, ParseMode
from telegram.ext import run_async, CommandHandler, MessageHandler, Filters

import haruka.modules.sql.antispam_sql as sql
from haruka import dispatcher, STRICT_ANTISPAM, spamwatch_api
from haruka.modules.helper_funcs.chat_status import user_admin, is_user_admin

from haruka.modules.tr_engine.strings import tld

GBAN_ENFORCE_GROUP = 6


def check_and_ban(update, user_id, should_message=True):
    chat = update.effective_chat
    message = update.effective_message
    try:
        if spamwatch_api != None:
            headers = {'Authorization': f'Bearer {spamwatch_api}'}
            resp = requests.get("https://api.spamwat.ch/banlist/{user_id}",
                                headers=headers,
                                timeout=5)
            if resp.status_code == 200:
                sw_ban = json.loads(resp.content)
                reason = sw_ban['reason']
                chat.kick_member(user_id)
                if should_message:
                    message.reply_text(tld(
                        chat.id, "antispam_spamwatch_banned").format(reason),
                                       parse_mode=ParseMode.HTML)
                    return
                else:
                    return
        else:
            return
    except:
        pass


@run_async
def enforce_gban(bot: Bot, update: Update):
    # Not using @restrict handler to avoid spamming - just ignore if cant gban.
    try:
        if sql.does_chat_gban(
                update.effective_chat.id) and update.effective_chat.get_member(
                    bot.id).can_restrict_members:
            user = update.effective_user
            chat = update.effective_chat
            msg = update.effective_message

            if user and not is_user_admin(chat, user.id):
                check_and_ban(update, user.id)
                return

            if msg.new_chat_members:
                new_members = update.effective_message.new_chat_members
                for mem in new_members:
                    check_and_ban(update, mem.id)
                    return

            if msg.reply_to_message:
                user = msg.reply_to_message.from_user
                if user and not is_user_admin(chat, user.id):
                    check_and_ban(update, user.id, should_message=False)
                    return
    except Exception:
        # Often timeout, bot kicked from chat, or bot is not in chat.
        return


@run_async
@user_admin
def antispam(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat
    if len(args) > 0:
        if args[0].lower() in ["on", "yes"]:
            sql.enable_antispam(chat.id)
            update.effective_message.reply_text(tld(chat.id, "antispam_on"))
        elif args[0].lower() in ["off", "no"]:
            sql.disable_antispam(chat.id)
            update.effective_message.reply_text(tld(chat.id, "antispam_off"))
    else:
        update.effective_message.reply_text(
            tld(chat.id,
                "antispam_err_wrong_arg").format(sql.does_chat_gban(chat.id)))


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


__help__ = True

ANTISPAM_STATUS = CommandHandler("antispam",
                                 antispam,
                                 pass_args=True,
                                 filters=Filters.group)

GBAN_ENFORCER = MessageHandler(Filters.all & Filters.group, enforce_gban)

dispatcher.add_handler(ANTISPAM_STATUS)

if STRICT_ANTISPAM:  # enforce GBANS if this is set
    dispatcher.add_handler(GBAN_ENFORCER, GBAN_ENFORCE_GROUP)
