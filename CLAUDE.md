# Forage — project rules for Claude Code

## Spending money on API calls

**Explicit human approval is required before spending money on LLM API calls.**

Every pipeline stage that calls the Anthropic or OpenAI API costs real money. Before running anything that triggers a paid API call — including but not limited to:

- `forage draft`, `forage reconsider`, `forage critique`, `forage iterate`
- Ad-hoc Python scripts that call `forage.llm.complete` (or the SDKs directly)
- Any experiment, test, or smoke-check that issues a live LLM request

…state what you are about to run, the expected cost, and wait for explicit user approval before executing. The user's prior approval of a specific command does NOT extend to subsequent calls.

**This applies even when `FORAGE_REPLAY=1` is set** — replay cache only avoids cost on calls that have previously been recorded; any new prompt, new segment, new model, or changed input will issue a live call.

Do not infer approval from a phrase like "keep going" or "next step." If the next step spends money, ask.

Refactors, CLI scaffolding, prompt edits, mechanical checks, validation, and reading/writing artifacts are all free — those don't need approval gates. The gate is specifically on live LLM invocation.
