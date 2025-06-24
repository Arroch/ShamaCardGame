import logging
import json
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
from game_logic import GameEngine, Player

# Настройка логгирования
logging.basicConfig(
    filename='game_logs.json',
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Состояния бота
LOBBY, GAME = range(2)

# Хранилище игровых сессий
game_sessions = {}

class GameSession:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.players = {}
        self.engine = GameEngine()
        self.invite_link = f"https://t.me/your_bot_name?start={chat_id}"

    def add_player(self, user_id, username, team=None):
        if user_id in self.players:
            return False
        
        player_id = len(self.players) + 1
        team = player_id % 2 or 2  # Распределение по командам: 1,2,1,2
        player = Player(player_id, team)
        player.user_id = user_id
        player.username = username
        
        self.players[user_id] = player
        self.engine.state.add_player(player)
        return True

    def start_game(self):
        if len(self.players) < 4:
            return False
        
        self.engine.start_game()
        return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    if args:
        # Присоединение к игре по ссылке
        chat_id = args[0]
        if chat_id in game_sessions:
            session = game_sessions[chat_id]
            if session.add_player(user.id, user.username):
                await update.message.reply_text(
                    f"Вы присоединились к игре! Ожидаем начала. Игроков: {len(session.players)}/4"
                )
                return LOBBY
            else:
                await update.message.reply_text("Вы уже в этой игре!")
        else:
            await update.message.reply_text("Игра не найдена")
    else:
        # Создание новой игры
        chat_id = str(update.effective_chat.id)
        game_sessions[chat_id] = GameSession(chat_id)
        session = game_sessions[chat_id]
        session.add_player(user.id, user.username)
        
        await update.message.reply_text(
            f"Игра создана! Пригласите друзей: {session.invite_link}\nИгроков: 1/4"
        )
        return LOBBY

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id not in game_sessions:
        await update.message.reply_text("Игра не найдена!")
        return LOBBY
    
    session = game_sessions[chat_id]
    if len(session.players) < 4:
        await update.message.reply_text("Недостаточно игроков! Нужно 4 человека")
        return LOBBY
    
    if session.start_game():
        # Рассылаем карты игрокам
        for user_id, player in session.players.items():
            keyboard = []
            for i, card in enumerate(player.hand):
                keyboard.append([InlineKeyboardButton(str(card), callback_data=f"play_{i}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text="Ваши карты:",
                reply_markup=reply_markup
            )
        
        # Отправляем сообщение о начале игры в чат
        await update.message.reply_text("Игра началась! Первый ход за игроком 1")
        return GAME
    else:
        await update.message.reply_text("Ошибка начала игры")
        return LOBBY

async def play_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    chat_id = str(update.effective_chat.id)
    card_index = int(query.data.split("_")[1])
    
    if chat_id not in game_sessions:
        await query.edit_message_text(text="Игра не найдена!")
        return GAME
    
    session = game_sessions[chat_id]
    player = session.players.get(user_id)
    if not player:
        await query.edit_message_text(text="Вы не участвуете в этой игре!")
        return GAME
    
    try:
        # Совершаем ход
        session.engine.play_turn(player.id, card_index)
        
        # Обновляем сообщение с картами
        keyboard = []
        for i, card in enumerate(player.hand):
            keyboard.append([InlineKeyboardButton(str(card), callback_data=f"play_{i}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="Ваши карты:",
            reply_markup=reply_markup
        )
        
        # Проверяем завершение игры
        if len(session.engine.state.tricks[1]) + len(session.engine.state.tricks[2]) == 9:
            # Подсчет и вывод результатов
            team1_score = session.engine.state.scores.get(1, 0)
            team2_score = session.engine.state.scores.get(2, 0)
            
            # Расчет финальных очков по правилам Шамы
            six_clubs_team = session.engine.state.six_clubs_team
            final_scores = {1: 0, 2: 0}
            
            for team in [1, 2]:
                points = team1_score if team == 1 else team2_score
                
                if team == six_clubs_team:
                    if points == 0:
                        final_scores[team] = 12
                    elif points < 30:
                        final_scores[team] = 6
                    elif points < 60:
                        final_scores[team] = 3
                    elif points == 60:
                        final_scores[team] = 2
                    else:
                        final_scores[team] = 0
                else:
                    if points == 0:
                        final_scores[team] = 6
                    elif points < 30:
                        final_scores[team] = 3
                    elif points < 60:
                        final_scores[team] = 1
                    else:
                        final_scores[team] = 0
            
            # Формируем результат
            result = (
                "Игра завершена!\n"
                f"Команда 1: {final_scores[1]} очков\n"
                f"Команда 2: {final_scores[2]} очков\n\n"
            )
            
            # Определение победителя
            if final_scores[1] > final_scores[2]:
                result += "Победила команда 1!"
            elif final_scores[2] > final_scores[1]:
                result += "Победила команда 2!"
            else:
                result += "Ничья!"
            await context.bot.send_message(chat_id=chat_id, text=result)
            return ConversationHandler.END
        
        # Уведомляем о следующем ходе
        next_player_id = session.engine.state.players[session.engine.state.current_player_index].id
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Следующий ход: игрок {next_player_id}"
        )
        
    except Exception as e:
        await query.edit_message_text(text=f"Ошибка: {str(e)}")
    
    return GAME

async def game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обработка игровых действий
    pass

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Игра отменена')
    return ConversationHandler.END

def main():
    application = Application.builder().token("YOUR_BOT_TOKEN").build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LOBBY: [
                CommandHandler('start', start),
                CommandHandler('startgame', start_game),
                CommandHandler('cancel', cancel)
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
