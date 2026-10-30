/* Load verified input sets from the active public course dataset. */
window.fetchScenarioPresets = (region, sport) => api.get("/api/scenarios/presets" + qs({ region, sport }));
