/* 시나리오 로컬 저장. 서버에는 저장하지 않습니다. */
const SC_KEY = "vgp_scenario";
const SC_BUNDLE_KEY = "vgp_selected_bundle";
function loadScenario() { try { const raw = localStorage.getItem(SC_KEY); return raw ? JSON.parse(raw) : null; } catch (e) { return null; } }
function saveScenario(sc) { try { localStorage.setItem(SC_KEY, JSON.stringify(sc)); return true; } catch (e) { return false; } }
function emptyScenario() {
  return { id: "local", title: "", regionCode: "", sport: "", demandGroups: [], supplyOptions: [], actions: [], budgetWon: null, mode: "capacity", notes: "" };
}
function uid(prefix) { return prefix + Math.random().toString(36).slice(2, 7); }
