from .cards import Catalog
from .domain import Card, Snapshot


def demo_snapshot(catalog: Catalog, stage: int = 0) -> Snapshot:
    # All economics below belong to a synthetic scenario, never to a detected live match.
    pool = [c for c in catalog.cards.values() if c.get("type") == "MINION" and c.get("techLevel") and c.get("isBattlegroundsPoolMinion")
            and c.get("battlegroundsNormalDbfId") is None and c.get("attack") is not None
            and c.get("health") is not None]
    pool.sort(key=lambda c: (c["techLevel"], c["id"]))
    chosen = pool[:10]
    if len(chosen) < 10:
        chosen = [{"id": f"DEMO_{i}", "name": f"演练随从 {i+1}", "attack": i+1,
                   "health": i+2, "techLevel": 1, "type": "MINION"} for i in range(10)]
    def card(index: int, position: int, cost: int | None = None):
        c = chosen[index]
        return Card(entity_id=index+10, card_id=c["id"], name=c["name"], attack=c["attack"], health=c["health"],
                    tier=c["techLevel"], cost=cost, position=position, races=c.get("races", []),
                    text=c.get("text", ""), mechanics=c.get("mechanics", []))
    board = [card(i, i+1) for i in range(3 + stage % 3)]
    return Snapshot(game_id="demo-session", source="demo", build=catalog.metadata.get("build"),
                    phase="recruit", player_id=1, turn=5 + stage, hero="演练英雄", health=max(8, 28-stage*3),
                    armor=5, gold=7 + stage % 3, tier=3, board=board, hand=[card(5, 1)],
                    shop=[card(i, i-5, 3) for i in range(6, 10)],
                    warnings=["演练局面：卡牌来自缓存，金币、身材与商店组合不代表真实对局。",
                              "基础规则建议；战斗模拟和当前启用卡池尚未验证。"])
