import os
import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler
from dotenv import load_dotenv

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
load_dotenv()
# Token del bot (da inserire)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 

# Stati per la conversazione
SELECTING_DAY = 1
SELECTING_TASK = 2
SELECTING_COFFEE_DAY = 3
CONFIGURING_TRASH = 4
ADDING_TRASH_TYPE = 5

# Costanti per i giorni della settimana in italiano
GIORNI = {
    "lunedi": 0,
    "martedi": 1,
    "mercoledi": 2,
    "giovedi": 3,
    "venerdi": 4
}

GIORNI_NOMI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]

# Funzione per convertire l'indice del giorno nel nome in italiano
def get_giorno_nome(indice):
    return GIORNI_NOMI[indice]

# Funzione per convertire il nome del giorno in italiano nell'indice
def get_giorno_indice(nome):
    nome_lower = nome.lower().replace('ì', 'i').replace('è', 'e')
    return GIORNI.get(nome_lower, 0)  # Default a lunedì se non trovato

# Inizializzazione del database SQLite
def init_db():
    conn = sqlite3.connect('trash_scheduler.db')
    cursor = conn.cursor()
    
    # Tabella per i tipi di spazzatura per ogni giorno
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trash_schedule (
        day_of_week INTEGER PRIMARY KEY,
        trash_types TEXT
    )
    ''')
    
    # Tabella per le prenotazioni della spazzatura
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trash_bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day_of_week INTEGER,
        user_id INTEGER,
        user_name TEXT,
        booking_date TEXT
    )
    ''')
    
    # Tabella per le prenotazioni della macchina del caffè
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS coffee_bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day_of_week INTEGER,
        user_id INTEGER,
        user_name TEXT,
        booking_date TEXT
    )
    ''')
    
    # Inizializza il calendario della spazzatura se vuoto
    cursor.execute('SELECT COUNT(*) FROM trash_schedule')
    if cursor.fetchone()[0] == 0:
        default_schedule = {
            0: "Indifferenziato",  # Lunedì
            1: "Organico",         # Martedì
            2: "Carta",            # Mercoledì
            3: "Organico",         # Giovedì
            4: "Vetro, Organico, Plastica",  # Venerdì
        }
        for day, trash_types in default_schedule.items():
            cursor.execute('INSERT INTO trash_schedule VALUES (?, ?)', (day, trash_types))
    
    conn.commit()
    conn.close()

# Funzioni per il database
def get_trash_types(day_of_week):
    conn = sqlite3.connect('trash_scheduler.db')
    cursor = conn.cursor()
    cursor.execute('SELECT trash_types FROM trash_schedule WHERE day_of_week = ?', (day_of_week,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "Nessuna raccolta"

def set_trash_types(day_of_week, trash_types):
    conn = sqlite3.connect('trash_scheduler.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE trash_schedule SET trash_types = ? WHERE day_of_week = ?', (trash_types, day_of_week))
    conn.commit()
    conn.close()

def add_trash_booking(day_of_week, user_id, user_name):
    conn = sqlite3.connect('trash_scheduler.db')
    cursor = conn.cursor()
    
    # Controlla se l'utente è già prenotato per questo giorno
    cursor.execute('SELECT id FROM trash_bookings WHERE day_of_week = ? AND user_id = ?', (day_of_week, user_id))
    if cursor.fetchone():
        conn.close()
        return False
    
    booking_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT INTO trash_bookings (day_of_week, user_id, user_name, booking_date) VALUES (?, ?, ?, ?)',
                  (day_of_week, user_id, user_name, booking_date))
    conn.commit()
    conn.close()
    return True

def add_coffee_booking(day_of_week, user_id, user_name):
    conn = sqlite3.connect('trash_scheduler.db')
    cursor = conn.cursor()
    
    # Controlla se l'utente è già prenotato per questo giorno
    cursor.execute('SELECT id FROM coffee_bookings WHERE day_of_week = ? AND user_id = ?', (day_of_week, user_id))
    if cursor.fetchone():
        conn.close()
        return False
    
    booking_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT INTO coffee_bookings (day_of_week, user_id, user_name, booking_date) VALUES (?, ?, ?, ?)',
                  (day_of_week, user_id, user_name, booking_date))
    conn.commit()
    conn.close()
    return True

def get_trash_bookings():
    conn = sqlite3.connect('trash_scheduler.db')
    cursor = conn.cursor()
    cursor.execute('SELECT day_of_week, user_name FROM trash_bookings ORDER BY day_of_week')
    bookings = {}
    for day, user_name in cursor.fetchall():
        if day not in bookings:
            bookings[day] = []
        bookings[day].append(user_name)
    conn.close()
    return bookings

def get_coffee_bookings():
    conn = sqlite3.connect('trash_scheduler.db')
    cursor = conn.cursor()
    cursor.execute('SELECT day_of_week, user_name FROM coffee_bookings ORDER BY day_of_week')
    bookings = {}
    for day, user_name in cursor.fetchall():
        if day not in bookings:
            bookings[day] = []
        bookings[day].append(user_name)
    conn.close()
    return bookings

def get_all_trash_types():
    conn = sqlite3.connect('trash_scheduler.db')
    cursor = conn.cursor()
    cursor.execute('SELECT day_of_week, trash_types FROM trash_schedule ORDER BY day_of_week')
    schedule = {day: types for day, types in cursor.fetchall()}
    conn.close()
    return schedule

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia un messaggio di benvenuto quando viene emesso il comando /start."""
    user = update.effective_user
    await update.message.reply_text(
        f"Ciao {user.first_name}! Benvenuto nel bot per la gestione della raccolta differenziata e della macchina del caffè.\n\n"
        "Comandi disponibili:\n"
        "/prenota - Prenota un giorno per portare giù la spazzatura\n"
        "/caffe - Prenota un giorno per pulire la macchina del caffè\n"
        "/visualizza - Visualizza tutte le prenotazioni attuali\n"
        "/calendario - Visualizza il calendario della raccolta differenziata e le prenotazioni rimanenti\n"
        "/configura - Configura i tipi di spazzatura per ogni giorno (solo amministratori)\n"
        "/aiuto - Mostra questo messaggio di aiuto"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia un messaggio di aiuto quando viene emesso il comando /aiuto."""
    await update.message.reply_text(
        "Comandi disponibili:\n"
        "/prenota - Prenota un giorno per portare giù la spazzatura\n"
        "/caffe - Prenota un giorno per pulire la macchina del caffè\n"
        "/visualizza - Visualizza tutte le prenotazioni attuali\n"
        "/calendario - Visualizza il calendario della raccolta differenziata e le prenotazioni rimanenti\n"
        "/configura - Configura i tipi di spazzatura per ogni giorno (solo amministratori)\n"
        "/aiuto - Mostra questo messaggio di aiuto"
    )

async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce il comando /prenota e mostra i giorni disponibili della prossima settimana."""
    keyboard = []
    today = datetime.now()
    # Trova il prossimo lunedì
    next_monday = today + timedelta(days=(7 - today.weekday()))
    
    # Crea bottoni per i giorni della prossima settimana (Lunedì - Venerdì)
    for day_idx in range(5):  # 0 = Lunedì, 4 = Venerdì
        day = next_monday + timedelta(days=day_idx)
        day_name = GIORNI_NOMI[day_idx]
        day_date = day_name + day.strftime(" %d/%m")  # es. "Lunedì 25/02"
        trash_types = get_trash_types(day_idx)
        keyboard.append([InlineKeyboardButton(
            f"{day_date} - {trash_types}", 
            callback_data=f"book_trash_{day_idx}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Seleziona un giorno per prenotarti a portare la spazzatura:", reply_markup=reply_markup)
    return SELECTING_DAY


async def coffee_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce il comando /caffe e mostra i giorni disponibili della prossima settimana."""
    keyboard = []
    today = datetime.now()
    # Trova il prossimo lunedì
    next_monday = today + timedelta(days=(7 - today.weekday()))
    
    # Crea bottoni per i giorni della prossima settimana (Lunedì - Venerdì)
    for day_idx in range(5):  # 0 = Lunedì, 4 = Venerdì
        day = next_monday + timedelta(days=day_idx)
        day_name = GIORNI_NOMI[day_idx]
        day_date = day_name + day.strftime(" %d/%m")  # es. "Lunedì 25/02"
        keyboard.append([InlineKeyboardButton(
            f"{day_date}", 
            callback_data=f"book_coffee_{day_idx}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Seleziona un giorno per prenotarti a pulire la macchina del caffè:", reply_markup=reply_markup)
    return SELECTING_COFFEE_DAY

async def handle_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione del giorno per la prenotazione."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_info = f"{user.first_name} {user.last_name if user.last_name else ''} (@{user.username})" if user.username else f"{user.first_name} {user.last_name if user.last_name else ''}"
    
    callback_data = query.data.split("_")
    booking_type = callback_data[1]  # trash o coffee
    selected_day = int(callback_data[2])
    
    # Usa il nome del giorno in italiano
    day_name = GIORNI_NOMI[selected_day]
    
    if booking_type == "trash":
        success = add_trash_booking(selected_day, user.id, user_info)
        trash_types = get_trash_types(selected_day)
        
        if success:
            message = f"Hai prenotato per {day_name}!\nTipo di rifiuti da raccogliere: {trash_types}"
        else:
            message = f"Sei già prenotato per portare la spazzatura {day_name}!"
    else:  # coffee
        success = add_coffee_booking(selected_day, user.id, user_info)
        
        if success:
            message = f"Hai prenotato per pulire la macchina del caffè {day_name}!"
        else:
            message = f"Sei già prenotato per pulire la macchina del caffè {day_name}!"
    
    await query.edit_message_text(message)
    return ConversationHandler.END

async def view_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Visualizza le prenotazioni rimanenti della settimana corrente e quelle della settimana prossima."""
    today = datetime.now()
    trash_bookings = get_trash_bookings()
    coffee_bookings = get_coffee_bookings()
    trash_schedule = get_all_trash_types()
    
    # Calcolo del giorno corrente della settimana (0 = lunedì, 6 = domenica)
    current_weekday = today.weekday()
    
    message = "📋 *Prenotazioni:*\n\n"
    
    # Parte 1: Prenotazioni rimanenti della settimana corrente (solo se non è venerdì o weekend)
    if current_weekday < 5:  # Siamo tra lunedì e giovedì
        message += "*🗓️ QUESTA SETTIMANA:*\n\n"
        
        # Calcola il lunedì di questa settimana
        days_since_monday = current_weekday
        this_monday = today - timedelta(days=days_since_monday)
        
        # Mostra solo i giorni rimanenti della settimana (da oggi a venerdì)
        for day_idx in range(current_weekday, 5):
            this_day = this_monday + timedelta(days=day_idx)
            formatted_date = this_day.strftime("%d/%m")
            day_name = GIORNI_NOMI[day_idx]
            
            trash_types = trash_schedule.get(day_idx, "Nessuna raccolta")
            
            message += f"*{day_name} {formatted_date}*\n"
            message += f"*Spazzatura:* {trash_types}\n"
            
            # Prenotazioni spazzatura
            if day_idx in trash_bookings and trash_bookings[day_idx]:
                message += "*Prenotati per la spazzatura:*\n"
                for user in trash_bookings[day_idx]:
                    message += f"• {user}\n"
            else:
                message += "• Nessuno prenotato per la spazzatura\n"
            
            # Prenotazioni macchina caffè
            message += "*Prenotati per la macchina del caffè:*\n"
            if day_idx in coffee_bookings and coffee_bookings[day_idx]:
                for user in coffee_bookings[day_idx]:
                    message += f"• {user}\n"
            else:
                message += "• Nessuno prenotato per la macchina del caffè\n"
            
            message += "\n"
        
        # Aggiungi una separazione tra le due sezioni
        message += "───────────────────\n\n"
    
    # Parte 2: Prenotazioni della settimana prossima
    message += "*🗓️ SETTIMANA PROSSIMA:*\n\n"
    
    # Trova il lunedì della prossima settimana
    days_to_next_monday = (7 - today.weekday()) % 7
    if days_to_next_monday == 0:
        days_to_next_monday = 7  # Se oggi è lunedì, vai al prossimo lunedì
    next_monday = today + timedelta(days=days_to_next_monday)
    
    for day_idx in range(5):  # 0 = Lunedì, 4 = Venerdì
        # Calcola la data per questo giorno della settimana prossima
        next_day = next_monday + timedelta(days=day_idx)
        formatted_date = next_day.strftime("%d/%m")
        day_name = GIORNI_NOMI[day_idx]
        
        trash_types = trash_schedule.get(day_idx, "Nessuna raccolta")
        
        message += f"*{day_name} {formatted_date}*\n"
        message += f"*Spazzatura:* {trash_types}\n"
        
        # Prenotazioni spazzatura
        if day_idx in trash_bookings and trash_bookings[day_idx]:
            message += "*Prenotati per la spazzatura:*\n"
            for user in trash_bookings[day_idx]:
                message += f"• {user}\n"
        else:
            message += "• Nessuno prenotato per la spazzatura\n"
        
        # Prenotazioni macchina caffè
        message += "*Prenotati per la macchina del caffè:*\n"
        if day_idx in coffee_bookings and coffee_bookings[day_idx]:
            for user in coffee_bookings[day_idx]:
                message += f"• {user}\n"
        else:
            message += "• Nessuno prenotato per la macchina del caffè\n"
        
        message += "\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def view_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Visualizza il calendario settimanale della raccolta differenziata e le prenotazioni rimanenti per la settimana corrente."""
    today = datetime.now()
    current_weekday = today.weekday()
    trash_schedule = get_all_trash_types()
    trash_bookings = get_trash_bookings()
    coffee_bookings = get_coffee_bookings()
    
    message = "📅 *Calendario settimanale della raccolta differenziata:*\n\n"
    
    # Prima visualizza il calendario completo
    for i in range(5):  # 0 = Lunedì, 4 = Venerdì
        day_name = GIORNI_NOMI[i]
        message += f"*{day_name}*: {trash_schedule.get(i, 'Nessuna raccolta')}\n"
    
    message += "\n📌 *Prenotazioni rimanenti per questa settimana:*\n\n"
    
    # Calcola il lunedì corrente
    days_since_monday = today.weekday()
    current_monday = today - timedelta(days=days_since_monday)
    
    # Mostra solo i giorni rimanenti della settimana corrente
    remaining_days = False
    for i in range(current_weekday, 5):  # Dal giorno corrente a venerdì
        next_day = current_monday + timedelta(days=i)
        formatted_date = next_day.strftime("%d/%m")
        day_name = GIORNI_NOMI[i]
        
        # Aggiungi informazioni solo per i giorni rimanenti
        message += f"*{day_name} {formatted_date}*\n"
        
        # Prenotazioni spazzatura
        if i in trash_bookings and trash_bookings[i]:
            message += "*Prenotati per la spazzatura:*\n"
            for user in trash_bookings[i]:
                message += f"• {user}\n"
        else:
            message += "• Nessuno prenotato per la spazzatura\n"
        
        # Prenotazioni macchina caffè
        message += "*Prenotati per la macchina del caffè:*\n"
        if i in coffee_bookings and coffee_bookings[i]:
            for user in coffee_bookings[i]:
                message += f"• {user}\n"
        else:
            message += "• Nessuno prenotato per la macchina del caffè\n"
        
        message += "\n"
        remaining_days = True
    
    # Se non ci sono giorni rimanenti in questa settimana
    if not remaining_days:
        message += "Non ci sono più giorni lavorativi rimanenti in questa settimana.\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def configure_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce il comando /configura e mostra i giorni disponibili."""
    keyboard = []
    
    for i in range(5):  # 0 = Lunedì, 4 = Venerdì
        day_name = GIORNI_NOMI[i]
        trash_types = get_trash_types(i)
        keyboard.append([InlineKeyboardButton(
            f"{day_name} - {trash_types}", 
            callback_data=f"config_{i}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Seleziona un giorno per configurare i tipi di spazzatura:", reply_markup=reply_markup)
    return CONFIGURING_TRASH

async def handle_day_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la selezione del giorno per la configurazione."""
    query = update.callback_query
    await query.answer()
    
    selected_day = int(query.data.split("_")[1])
    context.user_data["config_day"] = selected_day
    
    day_name = GIORNI_NOMI[selected_day]
    current_types = get_trash_types(selected_day)
    
    await query.edit_message_text(
        f"Configura i tipi di spazzatura per {day_name}\n"
        f"Attualmente: {current_types}\n\n"
        "Invia un messaggio con i tipi di spazzatura separati da virgola (es. 'Organico, Carta') "
        "o invia /annulla per annullare."
    )
    return ADDING_TRASH_TYPE

async def add_trash_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Aggiunge i tipi di spazzatura per un giorno."""
    if "config_day" not in context.user_data:
        await update.message.reply_text("Si è verificato un errore. Riprova con /configura.")
        return ConversationHandler.END
    
    day = context.user_data["config_day"]
    trash_types = update.message.text.strip()
    
    set_trash_types(day, trash_types)
    
    day_name = GIORNI_NOMI[day]
    
    await update.message.reply_text(f"Tipi di spazzatura per {day_name} aggiornati a: {trash_types}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancella la conversazione corrente."""
    await update.message.reply_text("Operazione annullata.")
    return ConversationHandler.END

async def set_commands(application):
    commands = [
        BotCommand("start", "Avvia il bot"),
        BotCommand("prenota", "Prenota un giorno per portare giù la spazzatura"),
        BotCommand("visualizza", "Visualizza tutte le prenotazioni"),
        BotCommand("caffe", "Prenota per la spazzatura"),
        BotCommand("calendario", "Visualizza il calendario della raccolta differenziata"),
        BotCommand("configura", "Configura i tipi di spazzatura per ogni giorno"),
        BotCommand("aiuto", "Mostra questo messaggio di aiuto"),
        # Aggiungi altri comandi qui
    ]
    
    await application.bot.set_my_commands(commands)

def main() -> None:
    """Avvia il bot."""
    # Inizializza il database
    init_db()
    
    # Crea l'applicazione
    application = ApplicationBuilder().token(TOKEN).build()
    # Imposta i comandi
    set_commands(application)
    
    # Crea il conversation handler per la prenotazione spazzatura
    trash_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("prenota", book_command)],
        states={
            SELECTING_DAY: [CallbackQueryHandler(handle_booking, pattern=r"^book_trash_")],
        },
        fallbacks=[CommandHandler("annulla", cancel)],
    )
    
    # Crea il conversation handler per la prenotazione caffè
    coffee_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("caffe", coffee_command)],
        states={
            SELECTING_COFFEE_DAY: [CallbackQueryHandler(handle_booking, pattern=r"^book_coffee_")],
        },
        fallbacks=[CommandHandler("annulla", cancel)],
    )
    
    # Crea il conversation handler per la configurazione
    config_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("configura", configure_command)],
        states={
            CONFIGURING_TRASH: [CallbackQueryHandler(handle_day_config, pattern=r"^config_")],
            ADDING_TRASH_TYPE: [MessageHandler(None, add_trash_type)],
        },
        fallbacks=[CommandHandler("annulla", cancel)],
    )
    
    # Aggiungi gli handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("aiuto", help_command))
    application.add_handler(CommandHandler("visualizza", view_bookings))
    application.add_handler(CommandHandler("calendario", view_schedule))
    application.add_handler(trash_conv_handler)
    application.add_handler(coffee_conv_handler)
    application.add_handler(config_conv_handler)
    
    # Avvia il bot
    application.run_polling()

if __name__ == "__main__":
    main()