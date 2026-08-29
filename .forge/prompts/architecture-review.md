# Prompt: Architecture Review

Use when asking an agent to review a proposed design or ADR. Intended
reviewers: Gemini (operational) and ChatGPT (design coherence).

---

You are reviewing a proposed design for **Forge**, an open-source AI coding
assistant CLI.

Read these first, and treat them as binding:

- `.forge/context/project.md`
- `.forge/context/architecture.md`
- `.forge/context/decisions.md`
- `docs/architecture/overview.md`

**Design under review:**

```text
<paste the design or link the ADR>
```

Review it against the following, and answer each explicitly:

1. **Architecture fit.** Does it respect the layering
   (presentation -> application -> domain, infrastructure implementing ports)?
   Name any place where the dependency direction would be inverted.
2. **ADR conflicts.** Does it contradict an accepted ADR? Quote the ADR.
3. **Failure modes.** List each realistic failure and the user-visible
   behaviour it should produce. Include: provider timeout, rate limit,
   malformed model output, unreadable or oversized file, missing
   configuration, not a git repository.
4. **Scalability.** What happens as input size grows? Name the first real
   bottleneck.
5. **Reliability.** What is safe to retry? What must be idempotent? Where is
   partial failure possible?
6. **Cost.** Token spend and request count per invocation, at least to an order
   of magnitude.
7. **Complexity.** Is anything here that YAGNI would remove? Is there a
   simpler design that meets the same requirement?
8. **Testability.** Can each piece be tested without a real provider call? If
   not, what seam is missing?

Rank every finding as **blocking**, **should fix**, or **consider**.

End with one line:

```text
VERDICT: approved | approved with changes | blocked
```

Constraints on your review:

- Be concrete. Name files, layers, and numbers.
- Respect the stage: Forge is a single-process CLI, not a distributed system.
- Do not propose a database, a vector store, or an agent framework. Those are
  excluded by decision.
- If you would need to break an ADR, say so and propose a superseding ADR
  rather than assuming the change.
