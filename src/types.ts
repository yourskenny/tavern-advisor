export interface Card {
  entity_id: number;
  card_id: string;
  name: string;
  type: string;
  attack: number | null;
  health: number | null;
  tier: number | null;
  cost: number | null;
  position: number;
  text: string;
  races: string[];
  mechanics: string[];
}
export interface Snapshot {
  id: string;
  game_id: string;
  observed_at: string;
  source: 'live' | 'demo' | 'import';
  build: string | null;
  phase: 'recruit' | 'combat' | 'ended' | 'unknown';
  player_id: number | null;
  turn: number | null;
  hero: string | null;
  health: number | null;
  armor: number | null;
  gold: number | null;
  tier: number | null;
  board: Card[];
  hand: Card[];
  shop: Card[];
  warnings: string[];
}
export interface Advice {
  rule: string;
  title: string;
  reason: string;
  confidence: string;
  action: string;
  entity_id: number | null;
  remaining_gold: number | null;
}
export interface Settings {
  mode: 'live' | 'demo';
  log_path: string;
  player_id: number | null;
  preference: 'balanced' | 'survival';
}
export interface Payload {
  settings: Settings;
  status: string;
  error: string | null;
  active_log: string | null;
  catalog: { build?: string; count?: number; sha256?: string };
  snapshot: Snapshot | null;
  advice: Advice[];
}
