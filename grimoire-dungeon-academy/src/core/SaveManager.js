import { GameState } from './GameState.js';
const KEY = 'gda-save-v1';
export const SaveManager = {
  exists() { return localStorage.getItem(KEY) !== null; },
  save(state) { localStorage.setItem(KEY, JSON.stringify(state.serialize())); },
  load() {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    try { return new GameState(JSON.parse(raw)); } catch { return null; }
  },
  clear() { localStorage.removeItem(KEY); }
};
