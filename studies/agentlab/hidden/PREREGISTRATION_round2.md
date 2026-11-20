# Round 2 pre-registration (written Thu Nov 19 18:44:52 UTC 2026 before any round-2 run, after round-1 search results were known)

Motivation: in round 1 (40 questions, 1-3 step chains, single-value answers) both search-tool agents matched or beat the
Voltex ceiling (Sonnet+search 38/40, Haiku+search 40/40, scripted Voltex 38/40). Hypothesis H2: EGM helps when answers are
sets that require joins or recursive expansion beyond what a capped keyword search returns per call.

Questions (20, same world): 5 x "list all ancestors of X", 5 x "list all siblings of X",
5 x "list everyone who is from region R", 5 x "how many people from region R work as P".
Target answer = what the knowledge base supports: stated facts plus everything the TRUE rules derive from the observations
(oracle closure). Also reported against the full hidden world.
Metrics: set questions -> F1 (precision, recall); count questions -> exact match and absolute error.
Tools: both tools get paging (kb_search ... --page N ; voltex "CMD" PAGE N), 30/40 lines per page as before.
Conditions: Sonnet+search, Sonnet+Voltex, Haiku+search, Haiku+Voltex, scripted Voltex. Same prompt except tool text.
Decision rule: report all results whatever they show; H2 is supported only if Voltex conditions beat their search
counterparts on mean F1 for both models.
