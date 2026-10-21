# Description Improvement Prompt Template

Below is a reference prompt template for improving a skill's description based on evaluation results.
Variables in `{curly_braces}` should be replaced with actual values.

---

You are optimizing a skill description for a skill called "{skill_name}". A "skill" has a title and description that the agent sees when deciding whether to use the skill. If triggered, the agent reads the full SKILL.md for details.

The description appears in the agent's "available_skills" list. When a user sends a query, the agent decides whether to invoke the skill based solely on the title and this description. Your goal: trigger for relevant queries, don't trigger for irrelevant ones.

Current description:
<current_description>
"{current_description}"
</current_description>

Current scores ({scores_summary}):
<scores_summary>

{Include FAILED TO TRIGGER section if any — queries that should have triggered but didn't}
{Include FALSE TRIGGERS section if any — queries that triggered but shouldn't have}
{Include PREVIOUS ATTEMPTS section if history exists — do NOT repeat, try something structurally different}

</scores_summary>

Skill content (for context):
<skill_content>
{skill_content}
</skill_content>

Write a new and improved description. Key principles:
- Generalize from failures to broader categories of user intent, don't enumerate specific queries
- Keep it 100-200 words max — descriptions are injected into ALL queries
- Use imperative form: "Use this skill for..." not "this skill does..."
- Focus on user intent, not implementation details
- Make it distinctive so it competes well against other skills
- Be creative — try different structures and wordings across iterations

Respond with ONLY the new description in <new_description> tags.

---

## History Format

When including previous attempts, format each as:

```
<attempt train={train_passed}/{train_total}, test={test_passed}/{test_total}>
Description: "the description text"
Train results:
  [PASS] "query text" (should_trigger=true)
  [FAIL] "query text" (should_trigger=false, but triggered)
</attempt>
```

## Shortening Rule

If the resulting description exceeds 1024 characters, ask for a rewrite under 1024 characters while preserving the most important trigger words and intent coverage.
