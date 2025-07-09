import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from .game_api import GameAPI  # Используем новый API слой

# Настройка логгирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())  # Только консольное логгирование

# Состояния бота
LOBBY, CHOOSE_TEAM, CHOOSE_TRUMP, GAME = range(4)

# Экземпляр GameAPI для управления игровыми сессиями
game_api = GameAPI()

# Вспомогательные структуры для хранения связи пользователь-сессия
user_sessions = {}  # user_id -> session_id
session_teams = {}  # session_id -> {team: [user_id]}

import time

def create_session_id(creator_id):
    return f"{int(time.time())}{creator_id}"

def get_available_team(session_id):
    """Возвращает доступную команду в сессии"""
    teams = session_teams.get(session_id, {1: [], 2: []})
    if len(teams[1]) < 2:
        return 1
    elif len(teams[2]) < 2:
        return 2
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    private_chat_id = update.effective_chat.id
    
    if args:
        # Присоединение к существующей игре
        session_id = args[0]
        
        # Проверяем доступные команды
        team = get_available_team(session_id)
        if not team:
            await update.message.reply_text("Все команды заполнены!")
            return ConversationHandler.END
        
        # Добавляем игрока в сессию через API
        try:
            # Получаем текущее состояние игры
            game_state = game_api.get_game_state(session_id)
            players = [p['name'] for p in game_state['players']]
            
            # Обновляем информацию о командах
            if session_id not in session_teams:
                session_teams[session_id] = {1: [], 2: []}
            session_teams[session_id][team].append(user.id)
            user_sessions[user.id] = session_id
            
            # Формируем список игроков в команде
            team_players = [p for p in players if p != user.username]
            
            await update.message.reply_text(
                f"Вы присоединились к команде {team}! Игроки в команде: {', '.join(team_players)}\n"
                f"Ожидаем начала игры. Игроков: {len(players)+1}/4"
            )
            return LOBBY
        except ValueError:
            await update.message.reply_text("Игра не найдена")
            return ConversationHandler.END
    else:
        # Создание новой игры
        session_id = create_session_id(user.id)
        user_sessions[user.id] = session_id
        session_teams[session_id] = {1: [user.id], 2: []}
        
        # Создаем новую игру через API
        game_api.start_new_game(session_id, [user.username])
        
        invite_link = f"https://t.me/ShamaGameBot?start={session_id}"
        await update.message.reply_text(
            f"Игра создана! Пригласите друзей: {invite_link}\n"
            f"Вы в команде 1. Игроков: 1/4"
        )
        return LOBBY

async def play_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    card_index = int(query.data.split("_")[1])
    
    # Получаем session_id пользователя
    session_id = user_sessions.get(user_id)
    if not session_id:
        await query.edit_message_text(text="Игра не найдена!")
        return GAME
    
    try:
        # Совершаем ход через API
        game_state = game_api.make_move(session_id, str(user_id), card_index)
        
        # Обновляем сообщение с картами
        keyboard = []
        player_state = next(p for p in game_state['players'] if p['id'] == str(user_id))
        for i, card in enumerate(player_state['hand']):
            keyboard.append([InlineKeyboardButton(card, callback_data=f"play_{i}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="Ваши карты:",
            reply_markup=reply_markup
        )
        
        # Обновляем состояние стола для всех игроков
        table_state = ", ".join(game_state['current_trick']) if game_state['current_trick'] else "пусто"
        for player in game_state['players']:
            await context.bot.send_message(
                chat_id=int(player['private_chat_id']),
                text=f"Козырь: {game_state['trump_suit']}\nНа столе: {table_state}"
            )
        
        # Проверяем завершение игры
        if game_state['status'] == 'completed':
            # Формируем результат
            result = (
                "Игра завершена!\n"
                f"Команда 1: {game_state['scores']['1']} очков\n"
                f"Команда 2: {game_state['scores']['2']} очков\n\n"
            )
            
            # Определение победителя
            if game_state['scores']['1'] > game_state['scores']['2']:
                result += "Победила команда 1!"
            elif game_state['scores']['2'] > game_state['scores']['1']:
                result += "Победила команда 2!"
            else:
                result += "Ничья!"
                
            # Рассылаем результаты всем игрокам
            for player in game_state['players']:
                await context.bot.send_message(
                    chat_id=int(player['private_chat_id']),
                    text=result
                )
            
            return ConversationHandler.END
        
        # Уведомляем о следующем ходе
        next_player_id = game_state['current_player_id']
        next_player = next(p for p in game_state['players'] if p['id'] == next_player_id)
        
        await context.bot.send_message(
            chat_id=int(next_player['private_chat_id']),
            text="Ваш ход! Выберите карту:"
        )
        
    except Exception as e:
        await query.edit_message_text(text=f"Ошибка: {str(e)}")
    
    return GAME
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Игра отменена')
    return ConversationHandler.END

async def choose_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора команды"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    team = int(data[1])
    session_id = data[2]
    user = query.from_user
    
    # Добавляем игрока в сессию через API
    try:
        # Обновляем информацию о командах
        if session_id not in session_teams:
            session_teams[session_id] = {1: [], 2: []}
        session_teams[session_id][team].append(user.id)
        user_sessions[user.id] = session_id
        
        # Получаем список игроков в команде
        game_state = game_api.get_game_state(session_id)
        team_players = [p['name'] for p in game_state['players'] if p['id'] in map(str, session_teams[session_id][team])]
        
        await query.edit_message_text(
            f"Вы присоединились к команде {team}! Игроки в команде: {', '.join(team_players)}\n"
            f"Ожидаем начала игры. Игроков: {len(game_state['players'])+1}/4"
        )
        return LOBBY
    except Exception:
        await query.edit_message_text("Не удалось присоединиться к команде. Возможно, команда уже заполнена.")
        return ConversationHandler.END

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик начала игры"""
    user = update.effective_user
    session_id = user_sessions.get(user.id)
    
    if not session_id:
        await update.message.reply_text("Игра не найдена!")
        return LOBBY
    
    try:
        # Получаем текущее состояние
        game_state = game_api.get_game_state(session_id)
        
        if len(game_state['players']) < 4:
            await update.message.reply_text("Недостаточно игроков! Нужно 4 человека")
            return LOBBY
        
        # Формируем информацию о командах
        team1_players = [p['name'] for p in game_state['players'] if p['id'] in map(str, session_teams[session_id][1])]
        team2_players = [p['name'] for p in game_state['players'] if p['id'] in map(str, session_teams[session_id][2])]
        
        match_info = (
            f"Игра №{session_id}\n"
            f"Команды: {', '.join(team1_players)} vs {', '.join(team2_players)}\n"
            f"Шама: {user.username}"
        )
        
        # Рассылаем уведомление всем игрокам
        for player in game_state['players']:
            await context.bot.send_message(
                chat_id=int(player['private_chat_id']),
                text=f"{match_info}\nИгра началась! Шама выбирает козырь..."
            )
        
        # Шама выбирает козырь
        keyboard = [
            [InlineKeyboardButton("♠", callback_data="trump_0")],
            [InlineKeyboardButton("♥", callback_data="trump_1")],
            [InlineKeyboardButton("♦", callback_data="trump_2")],
            [InlineKeyboardButton("♣", callback_data="trump_3")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Выберите козырь:",
            reply_markup=reply_markup
        )
        
        context.user_data['session_id'] = session_id
        return CHOOSE_TRUMP
    except Exception as e:
        await update.message.reply_text(f"Ошибка начала игры: {str(e)}")
        return LOBBY

async def choose_trump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора козыря"""
    query = update.callback_query
    await query.answer()
    
    trump_index = int(query.data.split("_")[1])
    session_id = context.user_data['session_id']
    suits = ["♠", "♥", "♦", "♣"]
    
    try:
        # Устанавливаем козырь через API
        game_state = game_api.make_move(session_id, "system", trump_index)
        
        # Уведомляем всех игроков о козыре
        for player in game_state['players']:
            await context.bot.send_message(
                chat_id=int(player['private_chat_id']),
                text=f"Козырь: {suits[trump_index]}\nНа столе: пусто"
            )
        
        # Рассылаем карты игрокам
        for player in game_state['players']:
            keyboard = []
            for i, card in enumerate(player['hand']):
                keyboard.append([InlineKeyboardButton(card, callback_data=f"play_{i}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=int(player['private_chat_id']),
                text="Ваши карты:",
                reply_markup=reply_markup
            )
        
        await query.edit_message_text(text=f"Выбран козырь: {suits[trump_index]}")
        return GAME
    except Exception as e:
        await query.edit_message_text(text=f"Ошибка: {str(e)}")
        return ConversationHandler.END

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("Ошибка: переменная окружения BOT_TOKEN не установлена")
        print("Пожалуйста, установите токен бота командой:")
        print("export BOT_TOKEN='ваш_токен'")
        return
    
    application = Application.builder().token(token).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LOBBY: [
                CommandHandler('start', start),
                CommandHandler('startgame', start_game),
                CommandHandler('cancel', cancel)
            ],
            CHOOSE_TEAM: [
                CallbackQueryHandler(choose_team, pattern="^team_")
            ],
            CHOOSE_TRUMP: [
                CallbackQueryHandler(choose_trump, pattern="^trump_")
            ],
            GAME: [
                CallbackQueryHandler(play_card),
                CommandHandler('cancel', cancel)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
