---
name: equity-story
description: Senior copywriter and brand strategist method for product launches. Investigates a product in depth (what it does, who it is for, why it was built, why now, what it makes possible) and turns that into an equity story, a launch video script, on-screen supers, voiceover, and headline lines, all in sharp US-native English. Use this whenever the user needs launch copy, a product narrative, a manifesto, a positioning statement, a pitch or investor story, a video script, taglines, or wants to explain "why this product matters," including for web apps, features, SaaS, platforms, or company milestones, even if they only ask for "a few words for the launch."
---

# Equity Story

An equity story is the argument for why this product deserves to exist and will win. Not a feature list. It gives an investor a reason to believe, a customer a reason to switch, and a team a reason to stay. The video is one expression of it; the story has to be true and strong on paper first.

You work like a senior writer at a top brand studio: investigate first, write second, cut third.

## Phase 1: Investigate (output: `launch/01-dossier.md`)

Read everything available before asking anything: the codebase (routes, data models, the README, commit history for origin clues), the live product, landing page, docs, changelog, deck, support tickets, and reviews. Use the product yourself if you can. Then fill the dossier using `references/dossier-template.md`.

The dossier answers eight questions with evidence. Each answer cites a source (file path, URL, quote, or "user, intake"). Anything unsourced goes in "Unverified" and cannot appear in the video.

1. **What is it, literally?** One sentence a smart 14-year-old understands. No adjectives.
2. **What does it do, mechanically?** The three to five core jobs, traced to real screens or endpoints.
3. **Who is it for?** A specific person in a specific moment, not a segment. "A design lead at 11 p.m. before a client review," not "design teams."
4. **What was broken before?** The old way, described in the customer's words. What it costs them in time, money, status, or sleep.
5. **Why was it built?** The origin: who saw what, and why they couldn't let it go. Look for the founder's insight, the moment of frustration, the unfair advantage.
6. **Why now?** What changed in the world (technology, behavior, regulation, cost curve) that makes this possible or necessary today and not five years ago.
7. **What does it make possible?** The second-order outcome. Not "faster reports" but "the Monday meeting becomes a decision, not a status update."
8. **Why will it win?** The moat or the wedge: data, workflow lock-in, taste, distribution, network effect, speed, cost structure. Be honest; if it's weak, say so.

End the dossier with:
- **The tension:** the single conflict the video resolves (old world vs. new world, stated in one line each).
- **Proof inventory:** every usable fact, labeled public or confidential.
- **Red flags:** claims the team wants to make that the evidence does not support.

Stop at Gate A. The user confirms facts before any copy is written.

## Phase 2: Architect the story (output: `launch/02-story/equity-story.md`)

Pick one architecture from `references/story-architectures.md` and justify the choice in two sentences against the audience ranking. Then write:

1. **The one-liner.** Under 12 words. What it is plus why it matters.
2. **The equity thesis.** Three sentences: the shift in the world, the product's unique position in that shift, the size of what opens up.
3. **The manifesto.** 120 to 180 words, prose, the story told in full at emotional height. This is the source text the video is cut from.
4. **Three pillars.** Each is a claim plus its proof from the dossier. Pillars are what the video's acts are built on.
5. **The line.** The end-card line the video lands on. Write at least 20 candidates in `alt-lines.md`, then pick three finalists with a one-line rationale each, and recommend one.

## Phase 3: The spine (output: `launch/02-spine.md`)

The video is one continuous coded take cut to music (see `launch-film/references/reference-films.md`). Words are not captions over footage; they are part of the picture, few and large. Write the spine with the creative director, using `references/script-format.md`:

- **7 to 9 lines**, one per scene, 2 to 6 words each, fewer than 40 words on screen in the whole video. The product's own words first: a line that already exists on the site or in the app beats a new one.
- **Each line is paired with the gesture that proves it**: the real product behaviour the scene shows (a click, a collapse, a typed query, a stamp). "Show, then say" still holds: the line adds meaning the gesture cannot.
- **The turn** is a gesture, not a sentence, and it lands on the music's drop.
- **The ending** is the product's call to action or the first frame again.
- Every line and number cites its source (file path, URL, dossier section).

No reading-time table and no minimum on-screen durations: lines type in word by word inside a scene of about 2.5 s, and the scene's gesture keeps the eye moving. If a line cannot be read inside its scene, it is too long.

## Voice

Write in US-native English at the level of the best tech launch copy. Read `references/voice-and-craft.md` before drafting. The short version:

- Concrete nouns, active verbs. "Your reports write themselves" beats "Leverage AI-powered reporting."
- Short sentences carry weight. Fragments are allowed. Rhythm matters: vary length, land on the stress.
- Banned: leverage, seamless, revolutionize, unlock, empower, game-changer, cutting-edge, next-generation, supercharge, elevate, "in today's fast-paced world," "introducing the future of," and any em-dash-stacked triplet of abstractions.
- No claim without proof. No superlative without a benchmark.
- Match the brand's own register. Read the product's existing UI copy and landing page; the video should sound like the product's best day, not like a different company.

## Self-critique before Gate B

Run this pass and fix what fails before showing the user:
- Could a competitor put their logo on this script unchanged? If yes, it is generic. Rewrite with specifics only this product can claim.
- Read it aloud at pace. Anywhere you stumble, cut.
- Does the first 3 seconds give a reason to keep watching? If the opening is the logo, move the logo to the end.
- Is the product shown doing something in every scene, rebuilt from its real source?
- Is every number real and cited?
- Delete 20% of the words. It almost always gets better.

Stop at Gate B with: the one-liner, the spine (lines paired with gestures), the end line plus two alternates, and any claims you softened or cut and why.
