# Rascunho de solicitação à FACEIT

**Status: não enviado.** Revise a identificação e envie pelo canal oficial de suporte/desenvolvedores da FACEIT. Não inclua sua chave de API.

**Subject:** Academic project — Season 8 EU final Challenger ranking and FACEIT Rating data

Hello FACEIT team,

I am developing a non-commercial academic project to identify statistically unusual player performance using the interquartile range (IQR).

Our intended population is all CS2 players who finished FACEIT Matchmaking Season 8 as Challenger in the EU region. We want to compare each player's average FACEIT Rating across eligible matches in that season. We mean the performance metric displayed next to the FACEIT symbol, not Elo, K/D, or an independently calculated rating.

We have successfully authenticated with the Data API. We tested:
- GET /rankings/games/cs2/regions/EU
- GET /players/{player_id}/history
- GET /players/{player_id}/games/cs2/stats
- GET /matches/{match_id}/stats

Historical matches and statistics such as ADR and K/D were returned, but we did not find FACEIT Rating in the sampled responses. The regional ranking endpoint has no documented season/date filter.

We also inspected the league linked to Europe 5v5 Queue. Its season number 8 corresponds to May 2024, so it does not appear to represent CS2 Matchmaking Season 8 in 2026.

Could you point us to a supported endpoint or provide an academic-use CSV/JSON export containing:

1. The final EU Challenger ranking for CS2 Matchmaking Season 8, including player IDs, nicknames, final positions and, if available, final Elo.
2. FACEIT Rating per player and match during Season 8, including player ID, match ID, date/time and rating; alternatively, official season-average ratings and the number of matches used per player.
3. Exact UTC season boundaries and the definition of the final Challenger population.
4. The rules used for the displayed average rating, including match eligibility, weighting, placement matches and missing ratings.
5. Any applicable access, attribution, retention or publication conditions for this academic project.

For a concrete example, we inspected player donk666 (e5e8e2a6-d716-4493-b949-e16965f41654) and match 1-02f245cf-0f54-40d0-8b5e-0aee19d8662c.

We do not need the proprietary formula or model behind the rating, only the resulting values and their aggregation definition.

Thank you,
[Your name]
[Course / institution, if applicable]
[Project repository URL, if public]

