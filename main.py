import os
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Configuration de Flask et activation du CORS pour autoriser l'accès depuis votre page HTML hébergée ailleurs
app = Flask(__name__)
CORS(app)

# Token du Bot Telegram (Remplacez par votre vrai token fourni par @BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8937672325:AAEYDCkLWV0KJoLNCCDm56cep9jFiFEjvrw")

# ==================== GESTION DE LA BASE DE DONNÉES (SQLITE) ====================
DB_NAME = "lamaisonblanche.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  # Table des profils avec statuts et montants
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            city TEXT,
            birthday TEXT,
            required_amount REAL DEFAULT 30000,
            paid_amount REAL DEFAULT 0,
            balance REAL DEFAULT 0,
            status TEXT DEFAULT 'red', -- red, yellow, green
            is_active INTEGER DEFAULT 1
        )
    """)
  # Table des coffres / motifs
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS vaults (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            motif TEXT NOT NULL,
            amount REAL DEFAULT 0
        )
    """)
  conn.commit()
  conn.close()


init_db()

# ==================== API POUR LE SITE WEB EXTERNE ====================


@app.route("/api/profiles", methods=["GET"])
def api_get_profiles():
  conn = sqlite3.connect(DB_NAME)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()
  cursor.execute("SELECT * FROM profiles WHERE is_active = 1")
  rows = cursor.fetchall()
  profiles = [dict(row) for row in rows]
  conn.close()
  return jsonify(profiles)


@app.route("/api/stats", methods=["GET"])
def api_get_stats():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT SUM(paid_amount), SUM(balance), COUNT(*) FROM profiles WHERE"
      " is_active = 1"
  )
  total_paid, total_balance, total_members = cursor.fetchone()
  conn.close()
  return jsonify({
      "total_paid": total_paid or 0,
      "total_balance": total_balance or 0,
      "total_members": total_members or 0,
  })


# ==================== LOGIQUE DES COULEURS DE STATUT ====================
def update_profile_status(cursor, profile_id):
  cursor.execute(
      "SELECT paid_amount, required_amount FROM profiles WHERE id = ?",
      (profile_id,),
  )
  row = cursor.fetchone()
  if row:
    paid, required = row
    if paid >= required:
      status = "green"  # Soldé totalement (Vert)
    elif paid > 0:
      status = "yellow"  # Soldé partiellement, reste un peu (Jaune)
    else:
      status = "red"  # Non payé / Non soldé (Rouge)
    cursor.execute(
        "UPDATE profiles SET status = ? WHERE id = ?", (status, profile_id)
    )


# ==================== INTERFACE BOT TELEGRAM (CLAVIERS 3D) ====================


def main_menu_keyboard():
  keyboard = [
      [
          InlineKeyboardButton(
              "👥 Gérer les Profils", callback_data="menu_profiles"
          )
      ],
      [
          InlineKeyboardButton(
              "💰 Gestion Trésorerie & Dépôts", callback_data="menu_treasury"
          )
      ],
      [
          InlineKeyboardButton(
              "🔒 Coffres & Motifs", callback_data="menu_vaults"
          )
      ],
      [InlineKeyboardButton("📊 Bilan Financier", callback_data="menu_stats")],
  ]
  return InlineKeyboardMarkup(keyboard)


# Commande /start (Image d'accueil + Message de bienvenue)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  welcome_text = (
      "🏛️ *Bienvenue dans l'espace de gestion de La Maison Blanche* 🌟\n\n"
      "Plateforme centralisée de pilotage des profils, cotisations et coffres."
      " Utilisez les boutons ci-dessous pour effectuer vos opérations :"
  )
  # Bannière photo d'accueil professionnelle
  banner_url = "https://images.unsplash.com/photo-1541872703-74c5e44368f9?q=80&w=1000&auto=format&fit=crop"

  if update.message:
    await update.message.reply_photo(
        photo=banner_url,
        caption=welcome_text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
  elif update.callback_query:
    query = update.callback_query
    await query.answer()
    await query.message.reply_photo(
        photo=banner_url,
        caption=welcome_text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# Gestion des clics sur les menus du Bot
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  data = query.data

  if data == "main_menu":
    await query.message.reply_text(
        "🏛️ *Menu Principal - La Maison Blanche* 🌟\nChoisissez une option :",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )

  elif data == "menu_profiles":
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Créer un Profil", callback_data="profile_add"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Liste & Gérer les Profils", callback_data="profile_list"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Restaurer un Profil", callback_data="profile_restore"
            )
        ],
        [InlineKeyboardButton("⬅️ Retour au Menu", callback_data="main_menu")],
    ]
    await query.message.reply_text(
        "👥 *Gestion des Profils* :",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

  elif data == "menu_treasury":
    keyboard = [
        [
            InlineKeyboardButton(
                "💵 Ajouter un Dépôt / Cotisation",
                callback_data="treasury_deposit",
            )
        ],
        [
            InlineKeyboardButton(
                "💸 Enregistrer un Retrait", callback_data="treasury_withdraw"
            )
        ],
        [InlineKeyboardButton("⬅️ Retour au Menu", callback_data="main_menu")],
    ]
    await query.message.reply_text(
        "💰 *Gestion de la Trésorerie* :\nSélectionnez une action financière :",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

  elif data == "menu_vaults":
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Créer un Nouveau Coffre", callback_data="vault_create"
            )
        ],
        [
            InlineKeyboardButton(
                "📥 Verser dans un Coffre", callback_data="vault_deposit"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Liste des Coffres", callback_data="vault_list"
            )
        ],
        [InlineKeyboardButton("⬅️ Retour au Menu", callback_data="main_menu")],
    ]
    await query.message.reply_text(
        "🔒 *Gestion des Coffres & Motifs* :",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

  elif data == "menu_stats":
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT SUM(paid_amount), SUM(balance), COUNT(*) FROM profiles WHERE"
        " is_active = 1"
    )
    total_paid, total_balance, total_members = cursor.fetchone()
    conn.close()

    stats_text = (
        f"📊 *Bilan Financier Global* :\n\n"
        f"👤 Membres totaux : *{total_members or 0}*\n"
        f"💰 Total Cotisations encaissées :"
        f" *{(total_paid or 0):,.0f} FCFA*\n"
        f"🏦 Solde global des coffres/comptes :"
        f" *{(total_balance or 0):,.0f} FCFA*\n"
    )
    keyboard = [[InlineKeyboardButton("⬅️ Retour au Menu", callback_data="main_menu")]]
    await query.message.reply_text(
        stats_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

  # --- CRÉATION DE PROFIL ---
  elif data == "profile_add":
    context.user_data["state"] = "waiting_profile_name"
    await query.message.reply_text(
        "📝 Veuillez entrer le **Nom complet** du nouveau membre :"
    )

  # --- LISTE DES PROFILS AVEC STATUTS COULEUR ---
  elif data == "profile_list":
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profiles WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
      await query.message.reply_text(
          "⚠️ Aucun profil enregistré pour le moment."
      )
      return

    for row in rows:
      # Indicateur visuel couleur (🔴 Rouge, 🟡 Jaune, 🟢 Vert)
      status_icon = (
          "🟢"
          if row["status"] == "green"
          else ("🟡" if row["status"] == "yellow" else "🔴")
      )
      text = (
          f"{status_icon} *{row['name']}*\n📞 Tél : {row['phone'] or 'N/A'}\n🏙️"
          f" Ville : {row['city'] or 'N/A'}\n🎂 Anniv :"
          f" {row['birthday'] or 'N/A'}\n💵 Cotisé :"
          f" {row['paid_amount']:,.0f} /"
          f" {row['required_amount']:,.0f} FCFA\n🏦 Solde :"
          f" {row['balance']:,.0f} FCFA"
      )
      kb = [
          [
              InlineKeyboardButton(
                  "🗑️ Supprimer ce Profil", callback_data=f"prof_del_{row['id']}"
              )
          ]
      ]
      await query.message.reply_text(
          text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
      )

  # --- RESTAURER UN PROFIL SUPPRIMÉ ---
  elif data == "profile_restore":
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profiles WHERE is_active = 0")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
      await query.message.reply_text("⚠️ Aucun profil désactivé à restaurer.")
      return

    keyboard = []
    for r in rows:
      keyboard.append([
          InlineKeyboardButton(
              f"♻️ Restaurer {r['name']}",
              callback_data=f"prof_res_{r['id']}",
          )
      ])
    await query.message.reply_text(
        "🔄 Sélectionnez le profil à réactiver :",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

  elif data.startswith("prof_res_"):
    prof_id = int(data.split("_")[-1])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE profiles SET is_active = 1 WHERE id = ?", (prof_id,))
    conn.commit()
    conn.close()
    await query.message.reply_text(
        "✅ Profil restauré avec succès et réaffiché sur le site web !"
    )

  # --- SÉLECTION DU MEMBRE POUR DÉPÔT / RETRAIT ---
  elif data in ["treasury_deposit", "treasury_withdraw"]:
    is_deposit = data == "treasury_deposit"
    context.user_data["action_type"] = "deposit" if is_deposit else "withdraw"
    context.user_data["state"] = "waiting_target_member_for_money"

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, paid_amount FROM profiles WHERE is_active = 1"
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
      await query.message.reply_text(
          "⚠️ Créez d'abord un profil avant d'effectuer un dépôt ou un retrait."
      )
      return

    keyboard = []
    for r in rows:
      keyboard.append([
          InlineKeyboardButton(
              f"👤 {r['name']} (Déjà versé: {r['paid_amount']:,.0f}F)",
              callback_data=f"sel_member_money_{r['id']}",
          )
      ])
    keyboard.append([InlineKeyboardButton("⬅️ Retour", callback_data="menu_treasury")])

    action_label = "un Dépôt / Ajout" if is_deposit else "un Retrait"
    await query.message.reply_text(
        f"💰 *Effectuer {action_label}* :\nSélectionnez le membre concerné :",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

  elif data.startswith("sel_member_money_"):
    member_id = int(data.split("_")[-1])
    context.user_data["target_member_id"] = member_id
    context.user_data["state"] = "waiting_money_amount"

    action_desc = (
        "montant à **ajouter** (Dépôt)"
        if context.user_data.get("action_type") == "deposit"
        else "montant à **retirer**"
    )
    await query.message.reply_text(
        f"🔢 Entrez le {action_desc} en FCFA (ex: 5000) :"
    )

  # --- GESTION DES COFFRES & MOTIFS ---
  elif data == "vault_create":
    context.user_data["state"] = "waiting_vault_motif"
    await query.message.reply_text(
        "🔒 Entrez le **motif / nom du coffre** (ex: *Sortie détente*, *Mariage*)..."
    )

  elif data == "vault_list":
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vaults")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
      await query.message.reply_text("⚠️ Aucun coffre/motif créé pour l'instant.")
      return

    text = "🔒 *Liste des Coffres & Motifs actifs* :\n\n"
    for r in rows:
      text += f"▪️ *{r['motif']}* : Solde = **{r['amount']:,.0f} FCFA**\n"
    await query.message.reply_text(text, parse_mode="Markdown")

  elif data.startswith("prof_del_"):
    prof_id = int(data.split("_")[-1])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE profiles SET is_active = 0 WHERE id = ?", (prof_id,)
    )
    conn.commit()
    conn.close()
    await query.message.reply_text(
        "🗑️ Profil désactivé avec succès (Il disparaît du site et peut être"
        " restauré)."
    )


# ==================== SAISIES TEXTUELLES ÉTAPE PAR ÉTAPE ====================


async def handle_text_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
  state = context.user_data.get("state")
  text = update.message.text.strip()

  if not state:
    return

  # 1. Création de profil
  if state == "waiting_profile_name":
    context.user_data["new_name"] = text
    context.user_data["state"] = "waiting_profile_phone"
    await update.message.reply_text(
        "📞 Entrez le **numéro de téléphone** du membre (ex: 0787985670) :"
    )

  elif state == "waiting_profile_phone":
    context.user_data["new_phone"] = text
    context.user_data["state"] = "waiting_profile_city"
    await update.message.reply_text(
        "🏙️ Entrez la **ville** de résidence (ex: Abidjan) :"
    )

  elif state == "waiting_profile_city":
    context.user_data["new_city"] = text
    context.user_data["state"] = "waiting_profile_birthday"
    await update.message.reply_text(
        "🎂 Entrez la **date d'anniversaire** (ex: 26 septembre) :"
    )

  elif state == "waiting_profile_birthday":
    context.user_data["new_birthday"] = text
    context.user_data["state"] = "waiting_profile_required"
    await update.message.reply_text(
        "💵 Entrez le **montant exigé** pour ce membre (ex: 30000) :"
    )

  elif state == "waiting_profile_required":
    try:
      required_amt = float(text)
      name = context.user_data.get("new_name")
      phone = context.user_data.get("new_phone")
      city = context.user_data.get("new_city")
      birthday = context.user_data.get("new_birthday")

      conn = sqlite3.connect(DB_NAME)
      cursor = conn.cursor()
      cursor.execute(
          """
                INSERT INTO profiles (name, phone, city, birthday,"
          " required_amount, paid_amount, balance, status)
                VALUES (?, ?, ?, ?, ?, 0, 0, 'red')
            """,
          (name, phone, city, birthday, required_amt),
      )
      conn.commit()
      conn.close()

      context.user_data.clear()
      await update.message.reply_text(
          f"✅ Profil de **{name}** créé avec succès ! Statut initial :"
          " 🔴 (Non payé). Visible sur le site web.",
          parse_mode="Markdown",
      )
    except ValueError:
      await update.message.reply_text(
          "⚠️ Veuillez entrer un nombre valide pour le montant exigé."
      )

  # 2. Saisie montant dépôt / retrait
  elif state == "waiting_money_amount":
    try:
      amount = float(text)
      member_id = context.user_data.get("target_member_id")
      action_type = context.user_data.get("action_type")

      conn = sqlite3.connect(DB_NAME)
      cursor = conn.cursor()

      if action_type == "deposit":
        cursor.execute(
            """
                    UPDATE profiles 
                    SET paid_amount = paid_amount + ?, balance = balance + ?"
            " WHERE id = ?
                """,
            (amount, amount, member_id),
        )
      else:
        cursor.execute(
            """
                    UPDATE profiles 
                    SET balance = balance - ? WHERE id = ?
                """,
            (amount, member_id),
        )

      # Actualisation automatique du statut (Rouge, Jaune, Vert)
      update_profile_status(cursor, member_id)

      conn.commit()
      conn.close()

      context.user_data.clear()
      await update.message.reply_text(
          "✅ Opération effectuée avec succès ! Le code couleur et les soldes"
          " sont mis à jour instantanément sur le site web.",
          parse_mode="Markdown",
      )
    except ValueError:
      await update.message.reply_text(
          "⚠️ Veuillez entrer un montant numérique valide."
      )

  # 3. Création coffre
  elif state == "waiting_vault_motif":
    motif = text
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vaults (motif, amount) VALUES (?, 0)", (motif,)
    )
    conn.commit()
    conn.close()

    context.user_data.clear()
    await update.message.reply_text(
        f"🔒 Le coffre **'{motif}'** a été créé avec succès !",
        parse_mode="Markdown",
    )


# ==================== LANCEMENT DU SERVEUR ET DU BOT ====================


def run_telegram_bot():
  application = ApplicationBuilder().token(BOT_TOKEN).build()

  application.add_handler(CommandHandler("start", start))
  application.add_handler(CallbackQueryHandler(button_handler))
  application.add_handler(
      MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_inputs)
  )

  print("🤖 Le bot Telegram est en cours d'exécution...")
  application.run_polling()


if __name__ == "__main__":
  import threading

  # Démarrage de l'API Flask sur le port 5000 en arrière-plan
  flask_thread = threading.Thread(
      target=lambda: app.run(
          host="0.0.0.0", port=5000, debug=False, use_reloader=False
      )
  )
  flask_thread.start()

  # Démarrage du Bot Telegram
  run_telegram_bot()
