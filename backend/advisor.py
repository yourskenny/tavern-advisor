from .domain import Advice, Snapshot


def recommend(state: Snapshot, preference: str = "balanced") -> list[Advice]:
    if state.phase != "recruit" or state.player_id is None or state.gold is None:
        return []
    suggestions: list[Advice] = []
    playable = [c for c in state.hand if c.type == "MINION"]
    if playable and len(state.board) < 7:
        card = max(playable, key=lambda c: (c.attack or 0) + (c.health or 0))
        suggestions.append(Advice(rule="open-board-slot", title=f"考虑打出 {card.name}",
                                 reason=f"场上 {len(state.board)}/7 个随从，手牌中有可补位随从；先检查战吼目标与结算顺序。",
                                 action="play", entity_id=card.entity_id, remaining_gold=state.gold))
    buyable = [c for c in state.shop if c.type == "MINION" and c.cost is not None
               and 0 <= c.cost <= state.gold and c.attack is not None and c.health is not None]
    if buyable and len(state.hand) < 10:
        # This is deliberately only a stat baseline; combat and synergy are not modeled.
        buyable.sort(key=lambda c: c.attack + c.health, reverse=True)
        card = buyable[0]
        suggestions.append(Advice(rule="known-cost-body-baseline", title=f"候选购买：{card.name}",
                                 reason=f"当前价格 {card.cost}，购买后剩余 {state.gold - card.cost} 金币；在已知价格的商店随从中，基础身材较高。未计入技能、法术或成长收益。",
                                 action="buy", entity_id=card.entity_id, remaining_gold=state.gold - card.cost))
    if preference == "survival" or (state.health is not None and state.health <= 15):
        suggestions.append(Advice(rule="survival-review", title="优先复核即时战力",
                                 reason="当前采用保分偏好或生命值较低。升级前检查下轮生存压力；缺少对手完整阵容，无法计算受伤或胜率。"))
    elif state.gold > 0:
        suggestions.append(Advice(rule="economy-review", title="核对升级与刷新费用",
                                 reason="有未使用金币。升级、刷新、冻结和英雄技能尚未完成费用与机制验证，暂不生成具体操作顺序。"))
    return suggestions[:3]
