# Chapter 1: What a Rasa Mantle agent is

**Goal:** find the three parts of the briefing agent in its folder, and say in plain words what each one does.

**You need first:** Chapter 0, so that the briefing agent's checkpoint folder is on your computer. You only read files here. Nothing runs, and no key or account is needed.

This chapter is short on purpose. It shows you the parts. A later "Now change it" step, where you change one part and check it, follows after the class.

## The three parts

A **Rasa Mantle agent** is a folder of plain files. Rasa Mantle reads them and runs the conversation. Three kinds of file matter most.

| Part | What it does | File in the folder |
|---|---|---|
| **Agent** | Says who the assistant is and how it talks | `project/agent.yml` |
| **Skill** | Says what to do for a traveler, and which tools it may call | `project/skills/briefing/skill.md` |
| **Tool** | A function the agent can ask to run, such as "find flights" | `briefing/mcp_app.py` |

A **tool** is a function the agent can ask to run. The agent does not read flight data itself. It asks a tool, and the tool returns the answer.

## Get to the folder

Set `REPO` to your clone, then go to the checkpoint folder from Chapter 0:

```bash
export REPO=~/rasa-community-resources
cd "$REPO/workshops/software-factories-masterclass/book/ready/ch00/demo"
```

## See how it works

1. Read the top of the skill. It lists the two tools this agent is allowed to call:

   ```bash
   sed -n 1,6p project/skills/briefing/skill.md
   ```

   You see the skill's name, a one-line description and an `import_tools` list with `find_flights` and `briefing`. The rest of the file is instructions in ordinary sentences: how to greet, what to ask, and what never to ask.

2. Read the whole skill once:

   ```bash
   cat project/skills/briefing/skill.md
   ```

   Look for three kinds of sentence. Some say when to call a tool. Some say what never to do, such as never inventing a flight. Some say how to talk to the traveler, such as asking "Where are you flying to?" instead of asking for a technical code.

3. Find the two tools in the code:

   ```bash
   grep -E "async def (briefing|find_flights)" briefing/mcp_app.py
   ```

   You see two lines. `find_flights` looks for flights already in the air. `briefing` starts a briefing for a chosen flight, checks on it and revises it.

4. Read what each tool tells the agent about itself:

   ```bash
   grep -n "strict_tool(" briefing/mcp_app.py
   ```

   You see three lines. The first defines the helper. The other two are the calls for the two tools, and the sentence inside each call is the tool's description. The agent reads that sentence to decide when to call the tool.

Now you can follow one question. The traveler says where they are heading. The skill says to call `find_flights`. The tool returns choices. The traveler picks one, and the skill says to call `briefing`. The cards come from the tool, never from the agent's own words.

## You are done when

Run this in the `demo` folder:

```bash
( set -e; ls -1 project/agent.yml project/skills/briefing/skill.md briefing/mcp_app.py; echo "ch01 OK" )
```

It lists the agent, the skill and the tool, then prints `ch01 OK`. If a file is missing, you are in the wrong folder or Chapter 0's checkpoint is incomplete. Run the `cd` command above again.

You can now point to the agent, the skill and the tool in the folder.

## What comes next

The "Now change it" half of this chapter, where you change the skill and check it, follows after the class. Chapter 2 shows where the cards get their data.
