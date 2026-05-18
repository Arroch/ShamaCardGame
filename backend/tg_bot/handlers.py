"""Обработчики команд и callback-запросов Telegram-бота."""

import uuid
import logging
from datetime import datetime

import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from bin.constants import GameConstants
from bin.core import InvalidPlayerAction
import tg_bot.state as S
from tg_bot.game import (
    start_game,
    send_player_cards,
    send_message_to_all_players,
    format_game_status,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _get_active_game(player_id: int):
    """Возвращает (match_id, match_state, engine) или None если игрок не в активной игре."""
    if player_id not in S.PLAYER_TO_GAME:
        return None
    match_id = S.PLAYER_TO_GAME[player_id]['id']
    if match_id not in S.ACTIVE_MATCHES:
        return None
    return match_id, S.ACTIVE_MATCHES[match_id], S.MATCH_ENGINES[match_id]


# ---------------------------------------------------------------------------
# Команды
# ---------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик /start. Также обрабатывает инвайт-ссылки ?start=join_<match_id>."""
    player_id   = update.effective_user.id
    first_name  = update.effective_user.first_name
    username    = update.effective_user.username

    player_data = await S.storage.get_or_create_player(player_id, username, first_name)
    if not player_data:
        logger.warning(f"Не удалось зарегистрировать игрока {player_id}")

    # --- Присоединение по инвайт-ссылке ---
    if context.args and context.args[0].startswith('join_'):
        match_id = context.args[0][5:]

        if match_id in S.WAITING_MATCHES:
            if player_id in S.WAITING_MATCHES[match_id]['players']:
                await update.message.reply_text(
                    f"Привет, {first_name}! Вы уже в этой игре. Ожидайте начала."
                )
                return

            if len(S.WAITING_MATCHES[match_id]['players']) >= 4:
                await update.message.reply_text(
                    f"Игра заполнена (4 игрока). Создайте новую через /create_game."
                )
                return

            # Добавляем игрока в список ожидающих
            S.WAITING_MATCHES[match_id]['players'][player_id] = player_data.copy()
            S.PLAYER_TO_GAME[player_id] = {
                'id': match_id,
                'status': 'waiting',
                'position': None,
            }
            await S.storage.log_event(player_id, username, "join_match", {"match_id": match_id})

            team1 = S.WAITING_MATCHES[match_id]['team_1']
            team2 = S.WAITING_MATCHES[match_id]['team_2']

            # Если обе команды не заполнены — предлагаем выбор
            if len(team1) < 2 and len(team2) < 2:
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("Команда 1", callback_data="team_1"),
                    InlineKeyboardButton("Команда 2", callback_data="team_2"),
                ]])
                await context.bot.send_message(
                    chat_id=player_id,
                    text=(
                        f"Выберите команду:\n"
                        f"Команда 1: {team1}\n"
                        f"Команда 2: {team2}\n"
                    ),
                    reply_markup=keyboard,
                )
            else:
                # Автоматически добавляем в команду с местом
                team    = '1' if len(team1) < 2 else '2'
                team_key = f'team_{team}'
                position = int(f"{team}{len(S.WAITING_MATCHES[match_id][team_key]) + 1}")
                S.WAITING_MATCHES[match_id][team_key].append(f'{first_name} ({username})')
                S.PLAYER_TO_GAME[player_id]['position'] = position

                players = S.WAITING_MATCHES[match_id]['players']
                for chat_id in players:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"🎮 {first_name} присоединился к игре!\n\n"
                            f"Участники ({len(players)}/4):\n"
                            f"Команда 1: {S.WAITING_MATCHES[match_id]['team_1']}\n"
                            f"Команда 2: {S.WAITING_MATCHES[match_id]['team_2']}\n"
                        ),
                    )
                if len(players) == 4:
                    await start_game(match_id, players)
            return

        if match_id in S.ACTIVE_MATCHES:
            if player_id in S.PLAYER_TO_GAME and S.PLAYER_TO_GAME[player_id]['id'] == match_id:
                await update.message.reply_text("Привет! Ваша игра уже идёт.")
            else:
                await update.message.reply_text("Эта игра уже началась. Создайте новую через /create_game.")
            return

        await update.message.reply_text(
            "Игра по этой ссылке уже не активна. Создайте новую через /create_game."
        )
        return

    # --- Обычный /start ---
    await update.message.reply_text(
        f"Привет, {first_name}! Добро пожаловать в игру «Шама».\n\n"
        f"Используйте /help для списка команд."
    )


async def create_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик /create_game."""
    player_id  = update.effective_user.id
    first_name = update.effective_user.first_name
    username   = update.effective_user.username
    bot_username = (await context.bot.get_me()).username

    if player_id in S.PLAYER_TO_GAME:
        await update.message.reply_text("Вы уже состоите в игре. Завершите её перед созданием новой.")
        game_id     = S.PLAYER_TO_GAME[player_id]['id']
        game_status = S.PLAYER_TO_GAME[player_id]['status']

        if game_status == 'waiting':
            players      = S.WAITING_MATCHES[game_id]['players']
            player_list  = "\n".join(f"• {p['name']}" for p in players.values())
            invite_link  = f"https://t.me/{bot_username}?start=join_{game_id}"
            await update.message.reply_text(
                f"Игра ожидает игроков:\n{player_list}\n\n"
                f"Пригласите друзей:\n{invite_link}"
            )
        else:
            match_state = S.ACTIVE_MATCHES[game_id]
            await update.message.reply_text(
                f"Текущая игра:\n"
                f"{match_state.players[GameConstants.PLAYER_1_1]} и "
                f"{match_state.players[GameConstants.PLAYER_1_2]} — счёт: "
                f"{match_state.match_scores[GameConstants.TEAM_1]}\n"
                f"{match_state.players[GameConstants.PLAYER_2_1]} и "
                f"{match_state.players[GameConstants.PLAYER_2_2]} — счёт: "
                f"{match_state.match_scores[GameConstants.TEAM_2]}\n"
                f"Козырь: {GameConstants.SUIT_SYMBOLS[match_state.trump]}, "
                f"хвалил: {match_state.players[match_state.first_player_index]}\n"
                f"Ход: {match_state.current_turn}"
            )
        return

    player_data = await S.storage.get_or_create_player(player_id, username, first_name)
    if not player_data:
        await update.message.reply_text("Ошибка при создании игрока. Попробуйте ещё раз.")
        return

    match_id = str(int(datetime.now().timestamp())) + str(uuid.uuid4())[:8]
    S.WAITING_MATCHES[match_id] = {
        'creator_id': player_id,
        'players':   {player_id: player_data.copy()},
        'team_1':    [f"{player_data['name']} ({player_data['username']})"],
        'team_2':    [],
        'timestamp': asyncio.get_event_loop().time(),
    }
    S.PLAYER_TO_GAME[player_id] = {
        'id':       match_id,
        'status':   'waiting',
        'position': GameConstants.PLAYER_1_1,
    }

    invite_link = f"https://t.me/{bot_username}?start=join_{match_id}"
    await S.storage.log_event(player_id, username, "create_game", {"match_id": match_id})
    await update.message.reply_text(
        f"🎮 {first_name} создал(а) новую игру!\n\n"
        f"Участники: • {first_name}\n\n"
        f"Пригласите друзей:\n{invite_link}\n\n"
        f"/start join_{match_id}"
    )


async def start_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик /start_game — форсированный старт для создателя.

    Fix #7: добавлены guard-проверки.
    """
    player_id = update.effective_user.id

    if player_id not in S.PLAYER_TO_GAME:
        await update.message.reply_text("Вы не состоите в ожидающей игре.")
        return
    match_id = S.PLAYER_TO_GAME[player_id]['id']
    if match_id not in S.WAITING_MATCHES:
        await update.message.reply_text("Ожидающая игра не найдена.")
        return
    players = S.WAITING_MATCHES[match_id]['players']
    if len(players) < 4:
        await update.message.reply_text(f"Нужно ещё {4 - len(players)} игрока(ов).")
        return
    await start_game(match_id, players)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Доступные команды:\n"
        "/start — Начать использование бота\n"
        "/help — Это сообщение\n"
        "/ping — Проверить работу бота\n"
        "/info — Информация о боте\n"
        "/create_game — Создать новую игру\n"
        "/status — Текущее состояние игры\n"
        "/stats — Ваша статистика\n"
        "/rules — Правила игры"
    )


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Понг! Бот работает.")


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_info = await context.bot.get_me()
    await update.message.reply_text(
        f"🤖 Бот: @{bot_info.username} (ID: {bot_info.id})\n\n"
        f"👤 Вы: {update.effective_user.first_name} "
        f"(@{update.effective_user.username or '—'}, ID: {update.effective_user.id})\n\n"
        f"💾 Хранилище: {S.storage.__class__.__name__}"
    )


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎮 Правила игры «Шама» 🎮\n\n"
        "36 карт, 2 команды по 2 игрока.\n\n"
        "Иерархия: 6♣ > J♣ > J♠ > J♥ > J♦ > козырные карты > масть первого хода.\n"
        "Козырь объявляет игрок с шамой (6♣).\n\n"
        "Правила хода:\n"
        "1. Ходить в масть первой карты; нет масти — козырем; нет козыря — любой картой.\n"
        "2. После 9 ходов подсчёт взяток.\n\n"
        "Матч до 12 очков — команда с 12+ проигрывает.\n\n"
        "/create_game — начать игру!"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player_id = update.effective_user.id

    if player_id in S.PLAYER_TO_GAME:
        entry = S.PLAYER_TO_GAME[player_id]
        if entry['status'] == 'active' and entry['id'] in S.ACTIVE_MATCHES:
            text = await format_game_status(S.ACTIVE_MATCHES[entry['id']])
            await update.message.reply_text(text)
        elif entry['status'] == 'waiting' and entry['id'] in S.WAITING_MATCHES:
            players = S.WAITING_MATCHES[entry['id']]['players']
            player_list = "\n".join(f"• {p['name']}" for p in players.values())
            await update.message.reply_text(
                f"🎮 Ожидаем игроков ({len(players)}/4):\n{player_list}"
            )
        else:
            await update.message.reply_text("Игра не найдена.")
    else:
        await update.message.reply_text(
            "Вы не состоите в игре.\n"
            "/create_game — создать, инвайт-ссылка — присоединиться."
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player_id    = update.effective_user.id
    player_stats = await S.storage.get_player_stats(player_id)

    if player_stats:
        await update.message.reply_text(
            f"📊 Статистика {player_stats['name']}:\n\n"
            f"Игр: {player_stats['games']}\n"
            f"Побед: {player_stats['wins']}\n"
            f"Процент побед: {player_stats['win_rate']}%\n"
            f"Взяток: {player_stats['total_tricks']}\n"
            f"Шама-ходов: {player_stats['total_shama_calls']}"
        )
    else:
        await update.message.reply_text(
            "Статистики нет. Сыграйте несколько партий!"
        )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Я понимаю только команды, начинающиеся с /\n"
        "Отправьте /help для списка команд."
    )


async def error_handler(update, context) -> None:
    logger.error(f"Ошибка при обработке {update}: {context.error}")
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Произошла ошибка при обработке запроса.",
        )


# ---------------------------------------------------------------------------
# Callback-обработчик
# ---------------------------------------------------------------------------

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Единый обработчик inline-кнопок: card_, trump_, team_."""
    query      = update.callback_query
    await query.answer()

    player_id  = query.from_user.id
    username   = query.from_user.username
    first_name = query.from_user.first_name
    data       = query.data

    # -----------------------------------------------------------------------
    # Выбор карты
    # -----------------------------------------------------------------------
    if data.startswith('card_'):
        # Fix #4: guard-проверка
        game = _get_active_game(player_id)
        if game is None:
            await query.edit_message_text("Вы не состоите в активной игре.")
            return
        match_id, match_state, match_engine = game
        player_position = S.PLAYER_TO_GAME[player_id]['position']

        try:
            card_index = int(data.split('_')[1])
        except (IndexError, ValueError):
            await query.message.reply_text("Неверный формат данных карты.")
            return

        try:
            status, player, card = match_engine.play_turn(player_position, card_index)

            await query.edit_message_text(
                text=f"{query.message.text}\n\nВы выбрали: {card}",
                reply_markup=None,
            )
            # Fix #8: event_data — словарь
            await S.storage.log_event(player_id, username, "play_card", {"card": str(card)})
            await send_message_to_all_players(match_state, f"🃏 {player.name} сыграл: {card}")

            if status == GameConstants.Status.TRICK_COMPLETED:
                _, winning_card, winning_player_index, trick_points = match_engine.complete_turn()
                winning_player = match_state.players[winning_player_index]
                await send_message_to_all_players(
                    match_state,
                    f"👑 {winning_player.name} забирает взятку с {winning_card}! "
                    f"Очков: {trick_points}",
                )

                if status == GameConstants.Status.GAME_COMPLETED:
                    await _handle_game_completed(match_id, match_state, match_engine)
                    return

                if match_state.status == GameConstants.Status.PLAYING_CARDS:
                    next_player = match_state.players[match_state.current_player_index]
                    await send_player_cards(next_player, match_state)
            else:
                next_player = match_state.players[match_state.current_player_index]
                await send_player_cards(next_player, match_state)

        except InvalidPlayerAction as e:
            logger.warning(f"Недопустимый ход: {e}")
            await query.message.reply_text(f"Недопустимый ход: {e}")
            await send_player_cards(match_state.players[player_position], match_state)
        except Exception as e:
            logger.error(f"Ошибка при ходе: {e}")
            await query.message.reply_text(f"Ошибка при ходе: {e}")

    # -----------------------------------------------------------------------
    # Выбор козыря
    # -----------------------------------------------------------------------
    elif data.startswith('trump_'):
        # Fix #4: guard-проверка
        game = _get_active_game(player_id)
        if game is None:
            await query.edit_message_text("Вы не состоите в активной игре.")
            return
        match_id, match_state, match_engine = game

        suit = data.split('_')[1]
        suit_symbol = GameConstants.SUIT_SYMBOLS.get(suit, '?')
        suit_labels = {
            'clubs': 'трефы', 'diamonds': 'бубны',
            'hearts': 'червы', 'spades': 'пики',
        }

        try:
            status, player_name, trump = match_engine.set_trump_by_player(
                match_state.first_player_index, suit
            )
            await query.edit_message_text(
                text=f"{query.message.text}\n\nКозырь: {suit_symbol} ({suit_labels.get(suit, '?')})",
                reply_markup=None,
            )
            # Fix #8: event_data — словарь
            await S.storage.log_event(player_id, username, "set_trump", {"trump": trump})
            await send_message_to_all_players(
                match_state,
                f"🃏 {player_name} выбрал козырь: {suit_symbol} ({suit_labels.get(suit, '?')})\n"
                f"Ходит игрок с шамой.",
            )
            await send_player_cards(match_state.players[match_state.current_player_index], match_state)
        except Exception as e:
            logger.error(f"Ошибка при установке козыря: {e}")
            await query.message.reply_text(f"Ошибка: {e}")

    # -----------------------------------------------------------------------
    # Выбор команды
    # -----------------------------------------------------------------------
    elif data.startswith('team_'):
        # Fix #4: guard
        if (player_id not in S.PLAYER_TO_GAME
                or S.PLAYER_TO_GAME[player_id]['id'] not in S.WAITING_MATCHES):
            await query.edit_message_text("Эта игра больше не активна.")
            return

        # Fix #5: предотвратить повторный выбор команды
        if S.PLAYER_TO_GAME[player_id]['position'] is not None:
            await query.edit_message_text("Вы уже выбрали команду.")
            return

        match_id = S.PLAYER_TO_GAME[player_id]['id']
        team     = data.split('_')[1]        # '1' or '2' — строка
        team_key = data                      # 'team_1' or 'team_2'

        # Fix #5: правильное переключение team при заполненной команде
        if len(S.WAITING_MATCHES[match_id][team_key]) >= 2:
            team     = '2' if team == '1' else '1'
            team_key = f'team_{team}'
            await query.edit_message_text(
                text=(
                    f"{query.message.text}\n\n"
                    f"Выбранная команда заполнена, добавили вас в Команду {team} "
                    f"({S.WAITING_MATCHES[match_id][team_key]})"
                ),
                reply_markup=None,
            )
        else:
            await query.edit_message_text(
                text=(
                    f"{query.message.text}\n\n"
                    f"Вы выбрали Команду {team} ({S.WAITING_MATCHES[match_id][team_key]})"
                ),
                reply_markup=None,
            )

        # Fix #5: position и append идут в правильный team_key
        position = int(f"{team}{len(S.WAITING_MATCHES[match_id][team_key]) + 1}")
        S.WAITING_MATCHES[match_id][team_key].append(f'{first_name} ({username})')
        S.PLAYER_TO_GAME[player_id]['position'] = position

        players = S.WAITING_MATCHES[match_id]['players']
        for chat_id in players:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🎮 {first_name} присоединился к игре!\n\n"
                    f"Участники ({len(players)}/4):\n"
                    f"Команда 1: {S.WAITING_MATCHES[match_id]['team_1']}\n"
                    f"Команда 2: {S.WAITING_MATCHES[match_id]['team_2']}\n"
                ),
            )

        # Fix #6: start_game вызывается без message; рассылка всем внутри start_game
        if len(players) == 4:
            await start_game(match_id, players)


# ---------------------------------------------------------------------------
# Внутренний хелпер завершения игры/матча
# ---------------------------------------------------------------------------

async def _handle_game_completed(match_id, match_state, match_engine):
    """Обрабатывает завершение раздачи и (если нужно) матча."""
    game_result   = match_engine.complete_game()
    status, scores, losed_team, _, losed_points_text = game_result

    await send_message_to_all_players(
        match_state,
        f"🏆 Раздача завершена!\n\n"
        f"Козырь хвалил: {match_state.players[match_state.first_player_index]}\n"
        f"Команда 1: {match_state.players[GameConstants.PLAYER_1_1]} и "
        f"{match_state.players[GameConstants.PLAYER_1_2]}: {scores[10]}\n"
        f"Команда 2: {match_state.players[GameConstants.PLAYER_2_1]} и "
        f"{match_state.players[GameConstants.PLAYER_2_2]}: {scores[20]}\n\n"
        f"Команда {losed_team // 10} получает {losed_points_text}\n\n"
        f"Счёт матча:\n"
        f"Команда 1: {match_state.match_scores[10]}\n"
        f"Команда 2: {match_state.match_scores[20]}",
    )

    if status == GameConstants.Status.MATCH_COMPLETED:
        match_engine.complete_match()
        losing_team  = 10 if match_state.match_scores[10] >= 12 else 20
        winning_team = 20 if losing_team == 10 else 10

        await send_message_to_all_players(
            match_state,
            f"🎉 Матч завершён!\n\n"
            f"Победила Команда {winning_team // 10}: "
            f"{match_state.players[winning_team + 1]} и "
            f"{match_state.players[winning_team + 2]}\n"
            f"Финальный счёт: {match_state.match_scores[10]} — {match_state.match_scores[20]}\n\n"
            f"/create_game — новая игра.",
        )

        del S.ACTIVE_MATCHES[match_id]
        del S.MATCH_ENGINES[match_id]

        # Fix #9: используем реальные данные из player.stat
        for pos, player in match_state.players.items():
            player_team = pos // 10 * 10
            won         = player_team == winning_team
            tricks      = player.stat.get('total_tricks', 0)
            shama_calls = player.stat.get('total_shama_calls', 0)
            await S.storage.update_player_stats(player.id, won, tricks, shama_calls)

        # Очищаем привязку игроков
        for player_id in list(S.PLAYER_TO_GAME.keys()):
            if S.PLAYER_TO_GAME[player_id]['id'] == match_id:
                del S.PLAYER_TO_GAME[player_id]

    elif status == GameConstants.Status.NEW_DEAL_READY:
        await send_message_to_all_players(
            match_state, "🃏 Новая раздача! Карты сдаются..."
        )
        match_engine.start_game()
        for player_position, player in match_state.players.items():
            await send_player_cards(
                player, match_state,
                is_first=(player_position == match_state.first_player_index),
            )
