# Using Prism with AI Coding Agents

Prism is an independent **second opinion** for code an AI agent just wrote. The agent that
authored a change is the worst judge of it — it shares the blind spots that produced the
bug. Prism reviews the diff with separate, specialized reviewers and a judge, then hands
back structured findings the agent can act on. Wired into the loop, it becomes a
self-review gate: the agent doesn't declare "done" until Prism passes.

This works because **`.prism/findings.json` is machine-readable** — your agent can run
Prism, read the findings, and fix them without a human in the loop.

## The loop

```
1. Agent makes a change on a branch
2. Run:  prism local --target main --config prism.yaml
3. Agent reads .prism/findings.json
4. Fix every critical + warning; use judgment on suggestions
5. Re-run until .prism/report.md says approved / approved_with_comments
```

The exit code makes step 5 mechanical: `prism local` returns nonzero until the verdict
clears your `policy.fail_on` threshold.

## The contract: `findings.json` + exit code

Your agent only needs two things.

**`.prism/findings.json`** — an array of findings. Each has `severity`
(`critical` · `warning` · `suggestion`), `file`, `line`, `title`, `explanation`,
`recommendation`, `confidence`, and `reviewer`. Full schema in the
[Usage Guide](usage.md#read-the-output).

**Exit code** — `0` while the verdict is below `policy.fail_on`; nonzero once it reaches
it. So a script can gate on `prism local ... && echo clean`.

A reasonable default policy for agents: **fix all `critical` and `warning` findings;
treat `suggestion`s as optional judgment calls.**

## Set up your agent

Drop one of these into your project's agent-instructions file. The instruction is the
same everywhere — only the filename differs by tool.

| Agent | File |
|-------|------|
| Claude Code | `CLAUDE.md` |
| Cursor | `.cursor/rules/` (or legacy `.cursorrules`) |
| Codex / OpenAI | `AGENTS.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |

### Drop-in instruction

````markdown
## Self-review with Prism

Before you tell me a change is complete, review it with Prism and address what it finds.

1. Run: `prism local --target main --config prism.yaml`
   (or `bin/prism local --target main` if using the Docker wrapper)
2. Read `.prism/findings.json` — a JSON array of findings.
3. Fix every finding with `"severity": "critical"` or `"severity": "warning"`.
   Use judgment on `"suggestion"` findings; if you skip one, say why.
4. Re-run until the decision in `.prism/report.md` is `approved` or
   `approved_with_comments`.

Do not claim the work is done until Prism passes. If a finding is a false positive,
explain your reasoning rather than silently ignoring it.
````

### Reading findings programmatically

If your agent prefers a command over parsing the file, these return just what matters:

```bash
# Count blocking findings (critical + warning)
jq '[.[] | select(.severity == "critical" or .severity == "warning")] | length' .prism/findings.json

# List them as "file:line  severity  title"
jq -r '.[] | select(.severity != "suggestion") | "\(.file):\(.line)\t\(.severity)\t\(.title)"' .prism/findings.json
```

## Why route through Prism instead of "review your own diff"

- **Independence.** Separate reviewer prompts (and often a different model/engine) catch
  what the authoring agent rationalized away.
- **Specialization.** A dedicated security reviewer with an explicit "what NOT to flag"
  list beats a generic "look for bugs" pass — far less noise.
- **A judge.** The coordinator dedupes overlapping findings, drops speculative ones, and
  reads the surrounding source to verify before deciding — so the agent acts on signal,
  not a firehose.
- **Structured output.** `findings.json` is built for an agent to consume and resolve
  item by item.

## Tips for good results

- **Keep diffs focused.** Smaller changes get sharper reviews and cheaper runs. Review per
  logical change, not once at the end of a huge branch.
- **Make `fail_on` match your bar.** Set `policy.fail_on: minor_issues` if you want the
  agent to also clear warning clusters, not just criticals.
- **Don't loop forever on suggestions.** Suggestions are advisory; a change that's
  `approved_with_comments` is shippable.
- **When stuck, read the transcript.** `.prism/runs/<reviewer>.jsonl` shows exactly what a
  reviewer saw and did — invaluable when a finding looks wrong.
- **Mind rate limits.** Each reviewer is a real subscription call. Spreading reviewers
  across both the `claude` and `codex` engines halves the pressure on either.

## Example: agent self-review session

```text
agent> (edits api/orders.py to add a search endpoint)
agent> prism local --target main --config prism.yaml
prism> Prism review: significant_concerns  (1 critical, 1 warning)
agent> (reads findings.json)
       critical  api/orders.py:42  SQL injection in order search
       warning   api/orders.py:55  N+1 query loads each customer in a loop
agent> (parameterizes the query; batches the customer fetch)
agent> prism local --target main --config prism.yaml
prism> Prism review: approved_with_comments  (0 critical, 0 warning)
agent> Done — Prism is clean. One suggestion left about naming, left as-is.
```
