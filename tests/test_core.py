import os
import time

import pytest

from backend.advisor import recommend
from backend.api import Service, Settings
from backend.cards import Catalog
from backend.domain import Card, Snapshot
from backend.logs import LogSession, LogTail, discover_log
from backend.store import Store


def log_line(message):
    return f"D 12:00:00.0000000 GameState.DebugPrintPower() - {message}\n"


def synthetic_log(combat=0, gold=True, bartender=True, friendly=True):
    messages = ["CREATE_GAME", "GameEntity EntityID=1", "tag=TURN value=5", "tag=STATE value=RUNNING",
                "Player EntityID=2 PlayerID=1 GameAccountId=[hi=1 lo=1]", "tag=CONTROLLER value=1",
                "tag=CARDTYPE value=PLAYER", "tag=HERO_ENTITY value=4", "tag=PLAYER_TECH_LEVEL value=3",
                f"tag=BACON_IN_COMBAT_PHASE value={combat}"]
    if gold:
        messages.extend(["tag=RESOURCES value=8", "tag=RESOURCES_USED value=2"])
    messages.extend(["Player EntityID=3 PlayerID=2 GameAccountId=[hi=1 lo=2]", "tag=CONTROLLER value=2",
                     "tag=CARDTYPE value=PLAYER", "tag=HERO_ENTITY value=5",
                     "FULL_ENTITY - Creating ID=4 CardID=HERO_DEMO", "tag=CARDTYPE value=HERO",
                     "tag=CONTROLLER value=1", "tag=ZONE value=PLAY", "tag=HEALTH value=30",
                     "tag=DAMAGE value=7", "tag=ARMOR value=5",
                     f"FULL_ENTITY - Creating ID=5 CardID={'TB_BaconShop_HERO_01' if bartender else 'OTHER_HERO'}",
                     "tag=CARDTYPE value=HERO", "tag=CONTROLLER value=2", "tag=ZONE value=PLAY",
                     "FULL_ENTITY - Creating ID=6 CardID=DEMO_MINION", "tag=CARDTYPE value=MINION",
                     "tag=CONTROLLER value=2", "tag=ZONE value=PLAY", "tag=ZONE_POSITION value=1",
                     "tag=ATK value=3", "tag=HEALTH value=4", "tag=BACON_OVERRIDE_BG_COST value=3"])
    if friendly:
        messages.extend(["FULL_ENTITY - Creating ID=7 CardID=", "tag=CONTROLLER value=1", "tag=ZONE value=HAND",
                         "SHOW_ENTITY - Updating Entity=7 CardID=DEMO_HAND", "tag=CARDTYPE value=MINION", "tag=ZONE value=HAND",
                         "tag=ATK value=2", "tag=HEALTH value=2"])
    return "".join(log_line(message) for message in messages)


@pytest.fixture
def catalog(tmp_path):
    return Catalog(tmp_path / "missing.json")


def test_upstream_parser_identity_shop_and_damage(catalog):
    session = LogSession(catalog, source="import")
    session.feed(synthetic_log())
    snapshot = session.snapshot()
    assert snapshot.player_id == 1
    assert snapshot.source == "import"
    assert snapshot.gold == 6
    assert snapshot.health == 23
    assert snapshot.armor == 5
    assert snapshot.phase == "recruit"
    assert [c.entity_id for c in snapshot.shop] == [6]
    assert [c.entity_id for c in snapshot.hand] == [7]
    assert any(a.action == "buy" and a.remaining_gold == 3 for a in recommend(snapshot))


@pytest.mark.parametrize("variant", [dict(combat=1), dict(gold=False), dict(friendly=False)])
def test_uncertain_or_combat_state_never_advises(catalog, variant):
    session = LogSession(catalog)
    session.feed(synthetic_log(**variant))
    assert recommend(session.snapshot()) == []


def test_opponent_board_not_misrepresented_as_shop(catalog):
    session = LogSession(catalog)
    session.feed(synthetic_log(bartender=False))
    assert session.snapshot().shop == []


def test_unknown_prices_and_full_hand_block_buy():
    card = Card(entity_id=1, card_id="X", name="X", attack=3, health=3)
    state = Snapshot(game_id="test", source="demo", phase="recruit", player_id=1, gold=10, shop=[card])
    assert not any(a.action == "buy" for a in recommend(state))
    card.cost = 3
    state.hand = [card] * 10
    assert not any(a.action == "buy" for a in recommend(state))


def test_partial_line_append_and_truncation(catalog, tmp_path):
    path = tmp_path / "Power.log"
    content = synthetic_log().encode()
    path.write_bytes(content[:-4])
    tail = LogTail(catalog, player_id=1)
    first = tail.poll(path)
    assert first.gold == 6
    assert tail.poll(path) is None
    with path.open("ab") as file:
        file.write(content[-4:] + log_line("TAG_CHANGE Entity=2 tag=RESOURCES_USED value=5").encode())
    second = tail.poll(path)
    assert second.gold == 3
    assert second.game_id == first.game_id
    path.write_bytes(synthetic_log(combat=1, gold=False, friendly=False).encode())
    third = tail.poll(path)
    assert third.phase == "combat"
    assert third.game_id != first.game_id


def test_invalid_log_taints_parse(catalog):
    session = LogSession(catalog)
    session.feed(synthetic_log() + "invalid line\n")
    with pytest.raises(ValueError, match="解析失败"):
        session.snapshot()


def test_session_discovery(tmp_path):
    folder = tmp_path / "new-session"
    folder.mkdir()
    path = folder / "Power.log"
    path.write_text("", encoding="utf-8")
    assert discover_log(str(tmp_path)) == path


def test_persist_roundtrip_and_deduplicate(tmp_path):
    store = Store(tmp_path / "history.sqlite3")
    state = Snapshot(game_id="game", source="demo", gold=8)
    store.save(state)
    store.save(state)
    assert len(store.recent()) == 1
    assert store.get(state.id) == state


def test_modes_do_not_leak_demo_into_live(tmp_path):
    service = Service(tmp_path)
    service.update(Settings(mode="demo"))
    assert service.payload()["snapshot"]["source"] == "demo"
    service.update(Settings(mode="live"))
    assert service.payload()["snapshot"] is None
    assert service.payload()["advice"] == []


def test_missing_file_clears_previous_live_snapshot(tmp_path):
    path = tmp_path / "Power.log"
    path.write_text(synthetic_log(), encoding="utf-8")
    service = Service(tmp_path / "data")
    service.update(Settings(log_path=str(path), player_id=1))
    service.poll()
    assert service.snapshot.source == "live"
    path.unlink()
    service.poll()
    assert service.snapshot is None
    assert service.payload()["advice"] == []


def test_stale_live_log_suppresses_advice_without_mutating_history(tmp_path):
    path = tmp_path / "Power.log"
    path.write_text(synthetic_log(), encoding="utf-8")
    old = time.time() - 180
    os.utime(path, (old, old))
    service = Service(tmp_path / "data")
    service.update(Settings(log_path=str(path), player_id=1))
    service.poll()
    assert service.payload()["status"] == "stale"
    assert service.payload()["advice"] == []
    assert "120" in service.payload()["snapshot"]["warnings"][-1]
    assert "120" not in service.snapshot.warnings[-1]


def test_tainted_log_error_persists_until_reconnect(tmp_path):
    path = tmp_path / "Power.log"
    path.write_text(synthetic_log() + "invalid\n", encoding="utf-8")
    service = Service(tmp_path / "data")
    service.update(Settings(log_path=str(path), player_id=1))
    service.poll()
    service.poll()
    assert service.payload()["status"] == "error"
    assert service.payload()["snapshot"] is None
    path.write_text(synthetic_log(), encoding="utf-8")
    service.reconnect()
    service.poll()
    assert service.payload()["status"] == "connected"
