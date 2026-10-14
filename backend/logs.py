import hashlib
from pathlib import Path
from uuid import uuid4

from hearthstone.enums import CardType, GameTag, State, Zone
from hslog.export import FriendlyPlayerExporter
from hslog.parser import LogParser

from .cards import Catalog
from .domain import Card, Snapshot


def discover_log(path: str) -> Path | None:
    root = Path(path)
    if root.is_file():
        return root if root.name.lower() == "power.log" else None
    if not root.is_dir():
        return None
    candidates = list(root.glob("Power.log")) + list(root.glob("*/Power.log"))
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def entity_card(entity, catalog: Catalog) -> Card:
    card_id = getattr(entity, "card_id", "")
    definition = catalog.get(card_id)
    tags = entity.tags
    attack = tags.get(GameTag.ATK)
    health = tags.get(GameTag.HEALTH)
    if health is not None:
        health = max(0, health - tags.get(GameTag.DAMAGE, 0))
    card_type = tags.get(GameTag.CARDTYPE)
    return Card(entity_id=entity.id, card_id=card_id, name=definition.get("name", card_id or "未知实体"),
                type=CardType(card_type).name if card_type is not None else definition.get("type", "INVALID"),
                attack=attack, health=health, tier=definition.get("techLevel"),
                cost=tags.get(GameTag.BACON_OVERRIDE_BG_COST),
                position=tags.get(GameTag.ZONE_POSITION, 0), text=definition.get("text", ""),
                races=definition.get("races", [definition["race"]] if definition.get("race") else []),
                mechanics=definition.get("mechanics", []))


def adapt_game(game, catalog: Catalog, game_id: str, source: str, player_id: int | None) -> Snapshot:
    warnings = ["基础策略未验证当前补丁；战斗模拟未接入。"]
    if not catalog.cards:
        warnings.append("卡牌数据库尚未同步。")
    else:
        warnings.append("卡牌数据 build 与客户端尚未核对；当前启用卡池未验证。")
    state = Snapshot(game_id=game_id, source=source, player_id=player_id,
                     build=catalog.metadata.get("build"), warnings=warnings)
    player = game.get_player(player_id) if player_id is not None else None
    if player is None:
        state.player_id = None
        state.warnings.append("无法确认友方玩家，请在连接设置中指定玩家编号。")
        return state
    tags = player.tags
    if GameTag.BACON_DUO_TEAM_ID in tags or tags.get(GameTag.BACON_DUO_TEAMMATE_PLAYER_ID):
        state.warnings.append("双人模式尚未支持。")
        return state
    state.tier = tags.get(GameTag.PLAYER_TECH_LEVEL)
    if state.tier is None:
        state.warnings.append("尚未确认酒馆模式与等级。")
        return state
    hero_entity = game.find_entity_by_id(tags.get(GameTag.HERO_ENTITY, 0))
    if hero_entity is not None:
        hero = entity_card(hero_entity, catalog)
        state.hero, state.health = hero.name, hero.health
        state.armor = hero_entity.tags.get(GameTag.ARMOR, 0)
    phase_flag = tags.get(GameTag.BACON_IN_COMBAT_PHASE, game.tags.get(GameTag.BACON_IN_COMBAT_PHASE))
    if game.tags.get(GameTag.STATE) == State.COMPLETE:
        state.phase = "ended"
    elif phase_flag == 1:
        state.phase = "combat"
    elif phase_flag == 0:
        state.phase = "recruit"
    else:
        state.warnings.append("阶段标签缺失，暂不生成操作建议。")
    # TURN is exposed verbatim; converting it to a recruitment round needs real-log validation.
    state.turn = game.tags.get(GameTag.TURN)
    if GameTag.RESOURCES in tags:
        state.gold = max(0, tags[GameTag.RESOURCES] - tags.get(GameTag.RESOURCES_USED, 0)
                         + tags.get(GameTag.TEMP_RESOURCES, 0))
    else:
        state.warnings.append("金币未知，暂停操作建议。")
    for entity in game.entities:
        if entity.tags.get(GameTag.CONTROLLER) != player_id:
            continue
        if entity.type == CardType.MINION and entity.zone == Zone.PLAY:
            state.board.append(entity_card(entity, catalog))
        elif entity.zone == Zone.HAND:
            state.hand.append(entity_card(entity, catalog))
    if state.phase == "recruit":
        bartenders = []
        for other in game.players:
            other_hero = game.find_entity_by_id(other.tags.get(GameTag.HERO_ENTITY, 0))
            if other_hero is not None and getattr(other_hero, "card_id", "").startswith("TB_BaconShop_HERO_01"):
                bartenders.append(other.player_id)
        if len(bartenders) == 1:
            for entity in game.entities:
                if (entity.tags.get(GameTag.CONTROLLER) == bartenders[0] and entity.zone == Zone.PLAY
                        and entity.type in (CardType.MINION, CardType.BATTLEGROUND_SPELL)):
                    state.shop.append(entity_card(entity, catalog))
        else:
            state.warnings.append("未唯一识别酒馆老板，商店内容未知。")
    if any(c.cost is None for c in state.shop):
        state.warnings.append("部分购买价格未知；不推测默认费用。")
    for cards in (state.board, state.hand, state.shop):
        cards.sort(key=lambda card: (card.position, card.entity_id))
    return state


class LogSession:
    def __init__(self, catalog: Catalog, source: str = "live", player_id: int | None = None):
        self.parser = LogParser()
        self.catalog = catalog
        self.source = source
        self.player_id = player_id
        self.current_tree = None
        self.game_id = str(uuid4())
        self.lines = 0
        self.error: str | None = None

    def feed(self, text: str):
        for line in text.splitlines():
            if not line.strip():
                continue
            self.lines += 1
            try:
                self.parser.read_line(line)
            except Exception as error:
                # A failed packet can invalidate later state; never advise from a tainted parse.
                self.error = f"第 {self.lines} 行解析失败：{type(error).__name__}。需要完整且受支持的 Power.log。"
                break

    def snapshot(self) -> Snapshot | None:
        if self.error:
            raise ValueError(self.error)
        if not self.parser.games:
            return None
        tree = self.parser.games[-1]
        if tree is not self.current_tree:
            self.current_tree = tree
            self.game_id = str(uuid4())
        if not tree.packets:
            return None
        # Do not flush a live parser: choices may span polling chunks.
        try:
            game = tree.export().game
        except Exception as error:
            self.error = f"实体树导出失败：{type(error).__name__}。请重连完整日志。"
            raise ValueError(self.error) from error
        if game is None:
            return None
        friendly = self.player_id
        if friendly is None:
            friendly = FriendlyPlayerExporter(tree).export()
        return adapt_game(game, self.catalog, self.game_id, self.source, friendly)


class LogTail:
    def __init__(self, catalog: Catalog, player_id: int | None = None):
        self.catalog = catalog
        self.player_id = player_id
        self.path: Path | None = None
        self.offset = 0
        self.pending = b""
        self.identity = None
        self.session = LogSession(catalog, player_id=player_id)

    def poll(self, path: Path) -> Snapshot | None:
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino, stat.st_ctime_ns)
        # Windows ctime is creation time; elsewhere it changes on writes, so inode suffices.
        identity = identity[:2]
        if path != self.path or identity != self.identity or stat.st_size < self.offset:
            self.path, self.identity, self.offset, self.pending = path, identity, 0, b""
            self.session = LogSession(self.catalog, player_id=self.player_id)
        if self.session.error:
            raise ValueError(self.session.error)
        if stat.st_size == self.offset:
            return None
        with path.open("rb") as file:
            file.seek(self.offset)
            chunk = file.read(1024 * 1024)
        self.offset += len(chunk)
        content = self.pending + chunk
        boundary = content.rfind(b"\n")
        if boundary < 0:
            self.pending = content
            return None
        self.pending = content[boundary + 1:]
        self.session.feed(content[:boundary + 1].decode("utf-8-sig", errors="replace"))
        return self.session.snapshot()


def fingerprint(snapshot: Snapshot) -> str:
    data = snapshot.model_dump(exclude={"id", "observed_at"})
    return hashlib.sha256(str(data).encode()).hexdigest()
