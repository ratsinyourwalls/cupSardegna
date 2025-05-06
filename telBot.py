#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""
First, a few callback functions are defined. Then, those functions are passed to
the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Example of a bot-user conversation using ConversationHandler.
Send /start to initiate the conversation.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
import traceback
from disponibilita import get_disponibilita
from secrets import token

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
    CallbackContext,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

CODICE_FISCALE, NRE, COMANDO, FILTRO = range(4)


reply_keyboard = [
    [
        "/visualizza_disponibilita",
        "/iscriviti_aggiornamenti",
    ],
    [
        "/filtra_iscrizione",
        "/cancella_iscrizione",
        "/lista_iscrizioni",
    ],
    ["Fine"],
]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)


def disp_show(disp):
    funk = disp["raw"].split("\n\n")[1].strip()
    res = f"{funk}\n{disp['data']}"
    if "nota" in disp:
        res += "[N]"
    return res


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation, display any stored data and ask user for input."""
    reply_text = """Con questo bot puoi prenotare al cup sardegna"""
    if context.user_data:
        reply_text += f"Prenotazioni:\n {','.join(context.user_data.keys())}."
    else:
        reply_text += ""

    reply_text += "\nDimmi il codice fiscale"
    await update.message.reply_text(reply_text)

    return CODICE_FISCALE


async def identifica_cf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Chiede codice fiscale."""
    text = update.message.text.upper()
    context.user_data["codice_fiscale"] = text
    reply_text = f"Ora il numero della ricetta elettronica"
    await update.message.reply_text(reply_text)

    return NRE


async def identifica_nre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Chiede codice ricetta elettronica."""
    text = update.message.text.upper()
    context.user_data["nre"] = text
    reply_text = f"Perfetto"
    await update.message.reply_text(reply_text, reply_markup=markup)

    return COMANDO


async def visualizza_disponibilita(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    reply_text = "Stiamo ottenendo le disponibilità..."
    await update.message.reply_text(reply_text)
    try:
        disp = get_disponibilita(
            context.user_data["codice_fiscale"], context.user_data["nre"]
        )
        if len(disp) > 0:
            reply_text = "Ecco le disponibilità:\n"
            i = 1
            for el in disp:
                reply_text += f"[{i}]: {disp_show(el)}\n"
                i += 1
                if len(reply_text) > 3400:
                    await update.message.reply_text(reply_text)
                    reply_text = ""
        else:
            reply_text = "Nessuna disponibilità"
    except Exception:
        reply_text = f"Errore Interno:\n{traceback.format_exc()}"
    await update.message.reply_text(reply_text)
    return COMANDO


async def cancella_iscrizione(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    cf = context.user_data["codice_fiscale"]
    nre = context.user_data["nre"]
    reply_text = "Iscrizione non trovata"
    if "iscrizioni" in context.user_data:
        if cf in context.user_data["iscrizioni"]:
            if nre in context.user_data["iscrizioni"][cf]:
                context.user_data["iscrizioni"][cf][nre]["job"].schedule_removal()
                del context.user_data["iscrizioni"][cf][nre]
                if len(context.user_data["iscrizioni"][cf]) == 0:
                    del context.user_data["iscrizioni"][cf]
                reply_text = "Iscrizione cancellata con successo"
    await update.message.reply_text(reply_text)
    return COMANDO


async def lista_iscrizioni(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    i = 0
    res = ""
    if "iscrizioni" in context.user_data:
        for cf in context.user_data["iscrizioni"].keys():
            for nre in context.user_data["iscrizioni"][cf].keys():
                filtri = ",".join(
                    context.user_data["iscrizioni"][cf][nre]["job"].data["filtri"]
                )
                if filtri != "":
                    res += f"[{i}] {cf} {nre} f:[{filtri}]\n"
                else:
                    res += f"[{i}] {cf} {nre} \n"
                i += 1
    if res == "":
        reply_text = "Nessuna iscrizione"
    else:
        reply_text = f"Iscrizioni:\n{res}"
    await update.message.reply_text(reply_text)
    return COMANDO


async def filtra_iscrizione_check(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    cf = context.user_data["codice_fiscale"]
    nre = context.user_data["nre"]
    reply_text = ""
    if "iscrizioni" in context.user_data:
        if cf in context.user_data["iscrizioni"]:
            if nre in context.user_data["iscrizioni"][cf]:
                reply_text = """Manda il filtro che vuoi aggiungere.
Un iscrizione ti manderà una notifica solo se compare almeno una delle parole filtro che hai selezionato (case insensitive)."""
    if reply_text == "":
        reply_text = "Iscrizione non trovata"
        await update.message.reply_text(reply_text)
        return COMANDO
    else:
        await update.message.reply_text(reply_text)
        return FILTRO


async def filtra_iscrizione(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cf = context.user_data["codice_fiscale"]
    nre = context.user_data["nre"]
    text = update.message.text.strip()
    reply_text = ""
    if "iscrizioni" in context.user_data:
        if cf in context.user_data["iscrizioni"]:
            if nre in context.user_data["iscrizioni"][cf]:
                context.user_data["iscrizioni"][cf][nre]["job"].data["filtri"].append(
                    text
                )
                reply_text = "Filtro aggiunto con successo"
    if reply_text == "":
        reply_text = "Iscrizione non trovata"

    await update.message.reply_text(reply_text)
    return COMANDO


async def controlla_iscrizione(context: CallbackContext):
    job = context.job
    data = context.job.data
    cf = data["codice_fiscale"]
    nre = data["nre"]
    filtri = data["filtri"]

    try:
        disp = get_disponibilita(cf, nre)
        res = ""
        reply_text = ""
        if len(disp) > 0:
            i = 1
            for el in disp:
                ok = False
                for filtro in filtri:
                    if filtro.lower() in el["raw"].lower():
                        ok = True
                if ok or len(filtri) == 0:
                    res += f"[{i}]: {disp_show(el)}\n"
                    i += 1
                    if len(res) > 3400:
                        reply_text = (
                            f"Aggiornamento sulla tua iscrizione {cf} {nre}:\n{res}"
                        )
                        await context.bot.send_message(job.chat_id, text=reply_text)
                        res = ""
        if len(res) > 0:
            if len(reply_text) == 0:
                reply_text = f"Aggiornamento sulla tua iscrizione {cf} {nre}:\n{res}"
            else:
                reply_text = res
            await context.bot.send_message(job.chat_id, text=reply_text)

    except Exception:
        reply_text = f"Errore Interno nel controllo dell iscrizione {cf} {nre}"
        reply_text += f"\n{traceback.format_exc()}"
        await context.bot.send_message(job.chat_id, text=reply_text)


async def iscriviti_aggiornamenti(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    chat_id = update.effective_message.chat_id
    cf = context.user_data["codice_fiscale"]
    nre = context.user_data["nre"]
    if "iscrizioni" not in context.user_data:
        context.user_data["iscrizioni"] = {}
    if cf not in context.user_data["iscrizioni"]:
        context.user_data["iscrizioni"][cf] = {}
    if nre in context.user_data["iscrizioni"][cf]:
        reply_text = "Iscrizione esiste già, cancellala prima"
        await update.message.reply_text(reply_text)
        return COMANDO
    else:
        context.user_data["iscrizioni"][cf][nre] = {}

    job = context.job_queue.run_repeating(
        controlla_iscrizione,
        60 * 30,
        first=60,
        chat_id=chat_id,
        data={"codice_fiscale": cf, "nre": nre, "filtri": []},
    )
    context.user_data["iscrizioni"][cf][nre]["job"] = job

    reply_text = "Iscrizione aggiunta con successo"
    await update.message.reply_text(reply_text)
    return COMANDO


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display the gathered info and end the conversation."""
    if "codice_fiscale" in context.user_data:
        del context.user_data["codice_fiscale"]
    if "nre" in context.user_data:
        del context.user_data["nre"]

    await update.message.reply_text(
        "Arrivederci",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    persistence = PicklePersistence(filepath="conversationbot")
    application = (
        Application.builder()
        .token("TOKEN")
        .token(token)
        .persistence(persistence)
        .build()
    )

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CODICE_FISCALE: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Fine$")),
                    identifica_cf,
                )
            ],
            NRE: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Fine$")),
                    identifica_nre,
                )
            ],
            COMANDO: [
                CommandHandler("visualizza_disponibilita", visualizza_disponibilita),
                CommandHandler("filtra_iscrizione", filtra_iscrizione_check),
                CommandHandler("iscriviti_aggiornamenti", iscriviti_aggiornamenti),
                CommandHandler("lista_iscrizioni", lista_iscrizioni),
                CommandHandler("cancella_iscrizione", cancella_iscrizione),
            ],
            FILTRO: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Fine$")),
                    filtra_iscrizione,
                )
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^Fine$"), done)],
        name="my_conversation",
        persistent=True,
    )

    application.add_handler(conv_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
