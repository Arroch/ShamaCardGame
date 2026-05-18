"""Игровая логика: запуск игры, отправка карт и сообщений игрокам."""

import logging

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from bin.constants import GameConstants
from bin.core import GameEngine, MatchState, Player
import client_tg_bot.state as S

logger = logging.getLogger(__name__)


async def send_message_to_all_players(match_state, text: str) -> None:
    """Отправляет сообщение всем живым игрокам матча."""
    for player in match_state.players.values():
        if player.id > 0:
            try:
                await S._bot.send_message(chat_id=player.id, text=text)
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения {player.name}: {e}")


async def send_player_cards(player, match_state, is_first: bool = False) -> None:
    """Отправляет игроку его карты и (если его ход) кнопки для хода."""
    if player.id < 0:
        return

    hand = player.get_hand()
    cards_text = " ".join(str(c) for c in hand)
    keyboard = None

    if is_first and match_state.status == GameConstants.Status.WAITING_TRUMP:
        message_text = (
            f"🃏 Ваши карты:\n{cards_text}\n\n"
            f"У вас шама (шестерка треф)! Выберите козырь:"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("♣ Трефы",  callback_data="trump_clubs"),
                InlineKeyboardButton("♦ Бубны",  callback_data="trump_diamonds"),
            ],
            [
                InlineKeyboardButton("♥ Червы",  callback_data="trump_hearts"),
                InlineKeyboardButton("♠ Пики",   callback_data="trump_spades"),
            ],
        ])

    elif (match_state.current_player_index
          and player.id == match_state.players[match_state.current_player_index].id):
        message_text = (
            f"🃏 Ваши карты:\n{cards_text}\n\n"
            f"Статус игры:\n"
            f"{match_state.players[GameConstants.PLAYER_1_1]} и "
            f"{match_state.players[GameConstants.PLAYER_1_2]} — счёт: "
            f"{match_state.match_scores[GameConstants.TEAM_1]}\n"
            f"{match_state.players[GameConstants.PLAYER_2_1]} и "
            f"{match_state.players[GameConstants.PLAYER_2_2]} — счёт: "
            f"{match_state.match_scores[GameConstants.TEAM_2]}\n"
            f"Козырь: {GameConstants.SUIT_SYMBOLS[match_state.trump]}, "
            f"хвалил: {match_state.players[match_state.first_player_index]}\n"
            f"Номер хода: {match_state.current_turn}\n"
            f"Карты на столе: {match_state.show_table()}\n"
            f"Сейчас ваш ход! Выберите карту:"
        )
        rows, row = [], []
        for i, card in enumerate(hand):
            row.append(InlineKeyboardButton(str(card), callback_data=f"card_{i}"))
            if len(row) == 3:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        keyboard = InlineKeyboardMarkup(rows)

    else:
        current_player_name = "?"
        if match_state.current_player_index:
            current_player_name = match_state.players[match_state.current_player_index].name
        message_text = (
            f"🃏 Ваши карты:\n{cards_text}\n\n"
            f"Сейчас ход игрока {current_player_name}."
        )

    try:
        await S._bot.send_message(
            chat_id=player.id,
            text=message_text,
            reply_markup=keyboard,
        )
        logger.info(f"Карты отправлены {player.name} (ID: {player.id})")
    except Exception as e:
        logger.error(f"Ошибка при отправке карт {player.name}: {e}")


async def format_game_status(match_state) -> str:
    """Форматирует строку статуса текущей игры."""
    status_labels = {
        GameConstants.Status.WAITING_PLAYERS:  "Ожидание игроков",
        GameConstants.Status.PLAYERS_ADDED:    "Все игроки добавлены",
        GameConstants.Status.CARDS_DEALT:      "Карты розданы",
        GameConstants.Status.WAITING_TRUMP:    "Ожидание выбора козыря",
        GameConstants.Status.TRUMP_SELECTED:   "Козырь выбран",
        GameConstants.Status.PLAYING_CARDS:    "Игра идёт",
        GameConstants.Status.PLAYED_CARD_1:    "1 карта на столе",
        GameConstants.Status.PLAYED_CARD_2:    "2 карты на столе",
        GameConstants.Status.PLAYED_CARD_3:    "3 карты на столе",
        GameConstants.Status.TRICK_COMPLETED:  "Кон завершён",
        GameConstants.Status.GAME_COMPLETED:   "Игра завершена",
        GameConstants.Status.NEW_DEAL_READY:   "Готовы к новой раздаче",
        GameConstants.Status.MATCH_COMPLETED:  "Матч завершён",
        GameConstants.Status.GAME_FINISHED:    "Игра полностью завершена",
    }
    text = f"🎮 Статус: {status_labels.get(match_state.status, 'Неизвестный')}\n\nИгроки:\n"
    for pos, player in match_state.players.items():
        team = "1" if pos // 10 == 1 else "2"
        line = f"• Команда {team}: {player.name}"
        if pos == match_state.first_player_index:
            line += " (шама)"
        if pos == match_state.current_player_index:
            line += " (ходит)"
        text += line + "\n"
    if match_state.trump:
        text += f"\nКозырь: {GameConstants.SUIT_SYMBOLS.get(match_state.trump, '?')}\n"
    text += (
        f"\nСчёт раздачи:  {match_state.game_scores[10]} — {match_state.game_scores[20]}\n"
        f"Счёт матча:    {match_state.match_scores[10]} — {match_state.match_scores[20]}\n"
        f"Ход: {match_state.current_turn}/9\n"
    )
    return text


async def start_game(match_id: str, players: dict) -> None:
    """Инициализирует и запускает игру, когда собрались 4 игрока.

    Fix #3: принимает только match_id/players (не message),
    рассылает сообщение о старте всем через _bot.
    Fix #2: использует S._bot вместо создания нового Bot().
    Fix #9: сохраняет матч в хранилище через storage.create_match.
    """
    logger.info(f"Начинаем игру {match_id}")
    try:
        match_state = MatchState()
        for player_data in players.values():
            player = Player(player_data['id'], player_data['name'])
            position = S.PLAYER_TO_GAME[player_data['id']]['position']
            match_state.add_player(position, player)
            S.PLAYER_TO_GAME[player_data['id']]['status'] = 'active'

        engine = GameEngine(match_state)
        engine.start_game()

        S.ACTIVE_MATCHES[match_id] = match_state
        S.MATCH_ENGINES[match_id] = engine
        del S.WAITING_MATCHES[match_id]

        # Сохраняем матч в хранилище
        player_ids = {
            S.PLAYER_TO_GAME[pd['id']]['position']: pd['id']
            for pd in players.values()
        }
        await S.storage.create_match(match_id, player_ids)

        team1 = [
            match_state.players[GameConstants.PLAYER_1_1].name,
            match_state.players[GameConstants.PLAYER_1_2].name,
        ]
        team2 = [
            match_state.players[GameConstants.PLAYER_2_1].name,
            match_state.players[GameConstants.PLAYER_2_2].name,
        ]
        start_text = (
            f"🎮 Игра начинается!\n\n"
            f"Команда 1: {', '.join(team1)}\n"
            f"Команда 2: {', '.join(team2)}\n\n"
            f"Карты розданы. Ожидаем выбор козыря."
        )
        for chat_id in players:
            await S._bot.send_message(chat_id=chat_id, text=start_text)

        for player_position, player in match_state.players.items():
            await send_player_cards(
                player, match_state,
                is_first=(player_position == match_state.first_player_index),
            )
    except Exception as e:
        logger.error(f"Ошибка при начале игры {match_id}: {e}")
        for chat_id in players:
            try:
                await S._bot.send_message(chat_id=chat_id, text=f"Ошибка при начале игры: {e}")
            except Exception:
                pass
