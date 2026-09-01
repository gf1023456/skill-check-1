# Trigger Evaluation Prompt Template

Below is a reference prompt template for evaluating whether a user query would trigger a specific skill.
Use this when delegating trigger evaluation to sub-agents (e.g., via a map tool).

---

You are testing whether a skill description would cause an agent to trigger (select and read) a skill for a given user query.

The skill under test:
- Name: {skill_name}
- Description: {skill_description}

The user query to evaluate:
<query>
{query}
</query>

Decide: would an agent with this skill in its available_skills list choose to invoke it for this query?

Consider:
- Does the query match the skill's described intent?
- Would the skill be the best tool for this request?
- Is there enough signal in the query to trigger this specific skill?
- Would a reasonable agent choose this skill over ignoring it or using a general-purpose approach?

Respond with ONLY a JSON object:
{"triggered": true/false}
