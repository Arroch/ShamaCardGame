"""Игровая логика: запуск игры, отправка карт и сообщений игрокам."""

import asyncio
import logging
from collections import Counter

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from bin.constants import GameConstants
from bin.core import GameEngine, MatchState, Player
import client_tg_bot.state as S

logger = logging.getLogger(__name__)

# Задержка между ходами бота (секунды) — чтобы игра читалась
BOT_MOVE_DELAY = 0.8


# ---------------------------------------------------------------------------
# Отправка сообщений
# ---------------------------------------------------------------------------

async def send_message_to_all_players(match_state, text: str) -> None:
    """Отправляет сообщение всем живым (не-бот) игрокам матча."""
    for player in match_state.players.values():
        if player.id > 0:
            try:
                await S._bot.send_message(chat_id=player.id, text=text)
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения {player.name}: {e}")


async def send_player_cards(player, match_state, is_first: bool = False) -> None:
    """Отправляет игроку его карты; бот-игроки (id < 0) игнорируются."""
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
            f"хвалил: {match_state.players.get(match_state.first_player_index, 'Unknown')}\n"
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


# ---------------------------------------------------------------------------
# Статус игры
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Завершение раздачи / матча
# ---------------------------------------------------------------------------

async def _handle_game_completed(match_id: str, match_state, engine) -> None:
    """Обрабатывает завершение раздачи: подсчёт очков, конец матча или новая раздача."""
    _, scores, losed_team, _, losed_points_text = engine.complete_game()

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

    if match_state.status == GameConstants.Status.MATCH_COMPLETED:
        engine.complete_match()
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

        for pos, player in match_state.players.items():
            if player.id > 0:  # Статистика только для живых игроков
                player_team = pos // 10 * 10
                await S.storage.update_player_stats(
                    player.id,
                    won=player_team == winning_team,
                    tricks=player.stat.get('total_tricks', 0),
                    shama_calls=player.stat.get('total_shama_calls', 0),
                )

        for pid in list(S.PLAYER_TO_GAME.keys()):
            if S.PLAYER_TO_GAME[pid]['id'] == match_id:
                del S.PLAYER_TO_GAME[pid]

    elif match_state.status == GameConstants.Status.NEW_DEAL_READY:
        await send_message_to_all_players(match_state, "🃏 Новая раздача! Карты сдаются...")
        engine.start_game()

        # Если шама у бота — автоматически выбираем козырь
        shama = match_state.players[match_state.first_player_index]
        if shama.id < 0:
            trump = _bot_pick_trump(match_state)
            engine.set_trump_by_player(match_state.first_player_index, trump)
            sym = GameConstants.SUIT_SYMBOLS[trump]
            await send_message_to_all_players(
                match_state, f"🤖 {shama.name} объявляет козырь: {sym}"
            )

        for player_position, player in match_state.players.items():
            await send_player_cards(
                player, match_state,
                is_first=(player_position == match_state.first_player_index),
            )


# ---------------------------------------------------------------------------
# Бот-игроки
# ---------------------------------------------------------------------------

def _bot_pick_trump(match_state) -> str:
    """Выбирает козырь для бота — масть с наибольшим количеством некозырных карт."""
    hand = match_state.players[match_state.first_player_index].hand
    regular = [
        c.suit for c in hand
        if c.rank != 'J' and not (c.rank == '6' and c.suit == GameConstants.CLUBS)
    ]
    if regular:
        return Counter(regular).most_common(1)[0][0]
    return GameConstants.HEARTS


async def auto_play_bots(match_id: str, match_state, engine) -> None:
    """Автоматически разыгрывает все последовательные ходы бот-игроков.

    Запускается после каждого хода живого игрока если следующий — бот.
    Продолжает до тех пор, пока:
    - не наступит ход живого игрока (отправляет ему карты и выходит),
    - или игра/матч не завершится.
    """
    _playing = (
        GameConstants.Status.TRUMP_SELECTED,
        GameConstants.Status.PLAYING_CARDS,
        GameConstants.Status.PLAYED_CARD_1,
        GameConstants.Status.PLAYED_CARD_2,
        GameConstants.Status.PLAYED_CARD_3,
    )

    while True:
        status = match_state.status

        # Игра завершена
        if status in (GameConstants.Status.GAME_FINISHED, GameConstants.Status.MATCH_COMPLETED):
            break

        # Ожидание козыря
        if status == GameConstants.Status.WAITING_TRUMP:
            shama = match_state.players[match_state.first_player_index]
            if shama.id >= 0:
                break  # Живой игрок выбирает козырь — выходим
            trump = _bot_pick_trump(match_state)
            engine.set_trump_by_player(match_state.first_player_index, trump)
            sym = GameConstants.SUIT_SYMBOLS[trump]
            await send_message_to_all_players(
                match_state, f"🤖 {shama.name} объявляет козырь: {sym}"
            )
            continue  # Проверяем следующий статус

        if status not in _playing:
            break

        current_idx = match_state.current_player_index
        current = match_state.players.get(current_idx)

        # Ход живого игрока — отправляем карты и выходим
        if current is None or current.id >= 0:
            if current:
                await send_player_cards(current, match_state)
            break

        # Бот выбирает первую допустимую карту
        valid_idx = next(
            (i for i in range(len(current.hand)) if engine.validate_card_play(current_idx, i)),
            None,
        )
        if valid_idx is None:
            logger.error(f"Бот {current.name} не нашёл допустимую карту")
            break

        await asyncio.sleep(BOT_MOVE_DELAY)
        _, player, card = engine.play_turn(current_idx, valid_idx)
        await send_message_to_all_players(match_state, f"🤖 {player.name} сыграл: {card}")

        if match_state.status == GameConstants.Status.TRICK_COMPLETED:
            _, winning_card, winning_player_idx, trick_points = engine.complete_turn()
            winning_player = match_state.players[winning_player_idx]
            await send_message_to_all_players(
                match_state,
                f"👑 {winning_player.name} забирает взятку ({winning_card}, {trick_points} очков)",
            )

            if match_state.status == GameConstants.Status.GAME_COMPLETED:
                await _handle_game_completed(match_id, match_state, engine)
                # _handle_game_completed либо завершил матч, либо начал новую раздачу
                # В обоих случаях продолжаем цикл — он сам проверит состояние


# ---------------------------------------------------------------------------
# Запуск игры
# ---------------------------------------------------------------------------

async def start_game(match_id: str, players: dict) -> None:
    """Инициализирует и запускает игру когда собрались 4 игрока (реальных + боты)."""
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

        # Сохраняем матч (только позиции живых игроков)
        player_ids = {
            S.PLAYER_TO_GAME[pd['id']]['position']: pd['id']
            for pd in players.values()
            if pd['id'] > 0
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
            f"Карты розданы."
        )
        for chat_id, pd in players.items():
            if pd['id'] > 0:
                await S._bot.send_message(chat_id=chat_id, text=start_text)

        # Если шама у бота — автовыбор козыря до отправки карт
        shama = match_state.players[match_state.first_player_index]
        if shama.id < 0:
            trump = _bot_pick_trump(match_state)
            engine.set_trump_by_player(match_state.first_player_index, trump)
            sym = GameConstants.SUIT_SYMBOLS[trump]
            await send_message_to_all_players(
                match_state, f"🤖 {shama.name} объявляет козырь: {sym}"
            )

        # Отправляем карты живым игрокам
        for player_position, player in match_state.players.items():
            await send_player_cards(
                player, match_state,
                is_first=(player_position == match_state.first_player_index),
            )

        # Если первый ход за ботом — запускаем автоигру
        current = match_state.players.get(match_state.current_player_index)
        if current and current.id < 0:
            await auto_play_bots(match_id, match_state, engine)

    except Exception as e:
        logger.error(f"Ошибка при начале игры {match_id}: {e}")
        for pd in players.values():
            if pd['id'] > 0:
                try:
                    await S._bot.send_message(chat_id=pd['id'], text=f"Ошибка при начале игры: {e}")
                except Exception:
                    pass
