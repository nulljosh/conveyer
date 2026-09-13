# Conveyer Technical Whitepaper

**v0.1.0** | September 2026

Most "AI plays a game" demos either script a fixed strategy or hand a vision model
screenshots and hope it guesses well. Conveyer exists to test something harder and more
honest: can a model actually reason about a complex, unforgiving system using the same
structured information a real player would want, and adapt when its plan breaks. An LLM
plays Factorio for real, against a real headless server, through the game's own Lua/RCON
console. No screenshots, no vision model guessing at pixels, because Factorio already
exposes its state as data and throwing that away to make the model squint at pixels would
be strictly worse engineering. Full structured game state in, Python code out.

## The mechanic

Every turn is the same loop, over and over:

1. The model gets the last action's stdout/stderr as its observation, what it printed, or
   what broke.
2. It writes a short Python snippet: place an entity, connect a belt, set a recipe, check an
   inventory.
3. That snippet runs inside [FLE](https://github.com/JackHopkins/factorio-learning-environment)'s
   gym environment, which sends it through the Lua/RCON bridge into a real, running,
   headless Factorio server.
4. Whatever the game returns, a placed entity, a crafted item, or a real Factorio exception, becomes the next observation.

That's the whole engine. No hidden state machine, no hardcoded build plan, because either
one would mean the model isn't really deciding anything, just filling in blanks in a script
someone already wrote. The model reads what actually happened and decides what to do next,
the same way a person would if they could only see stdout.

FLE already solved the plumbing this needed: the Docker orchestration of headless servers, the
Lua mod that exposes game state as structured Python objects, the task suite and reward
functions for measuring throughput. Building that layer again from scratch would be pure
duplicated effort with no research value. Conveyer is the agent loop that sits on top of it and
drives it, one turn at a time.

## Why this is harder than it sounds

Factorio has no undo button and no forgiving physics engine. An entity either fits on that
tile or it doesn't. A recipe is set or it isn't. There's no partial credit for a transport belt
pointed the wrong way. That means every mistake the model makes comes back as a real error
message from a real running simulation, not a graded score, and the model has to read that
error, understand what it actually means, and fix the one thing that's wrong without
abandoning everything it already built.

That turns out to be the actual hard part. Getting a model to write syntactically valid API
calls is easy. Getting it to treat its own build as a persistent structure worth protecting, rather than restarting from scratch every time something breaks, is not. Most of the work
here has been narrowing that gap: catching the exact way a model goes wrong (guessing raw
coordinates, hallucinating entity names, discarding a working drill after one bad line) and
turning each failure into an explicit rule instead of hoping the next run gets lucky, because
a rule fixes the failure mode for every future run and luck fixes nothing.

## Status

The loop is verified end to end: real code, run against a real server, real errors read and
acted on. A model has placed a working `BurnerMiningDrill` on real ore and kept extending the
same build across multiple turns instead of starting over, which is the specific behavior this
project set out to prove is possible. A complete self-sustaining base, drill, furnace,
assembler, output, is still in progress. See `roadmap.md` for the current state and what's
next.

## License

MIT 2026, Joshua Trommel. Factorio is property of Wube Software; this project is unaffiliated
and does not distribute the game.
