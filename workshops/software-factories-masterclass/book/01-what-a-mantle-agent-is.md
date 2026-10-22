> **22 October revision:** Start with [the participant guide](../PARTICIPANT-GUIDE.md) for the three-hour route, current API distinctions, and platform requirements. These chapters are reference exercises; their checks do not certify the complete voice-to-build-to-voice journey.

# Chapter 1: What a Rasa Mantle agent is

A traveler asks the agent a plain question and four cards come back. One file told the agent what to ask, and another fetched the flight. In about 10 minutes you'll find both, and the third part that ties them together, so you know where to look when the agent misbehaves.

Time: about 10 minutes. You need: the Chapter 0 ready folder and a terminal. You only read files here, so there's no key or account. This chapter has no "Now change it" step. That step comes after the class.

You're done when the listing command at the end prints `ch01 OK`. If you get stuck, open `book/ready/ch00/demo` and run the commands from there.

## The three parts

A **Rasa Mantle agent** is a folder of plain files. Rasa Mantle reads them and runs the conversation. Three kinds of file matter most.

| Part | What it does | File in the folder |
|---|---|---|
| **Agent** | Says who the assistant is and how it talks | `project/agent.yml` |
| **Skill** | Says what to do for a traveler, and which tools it may call | `project/skills/briefing/skill.md` |
| **Tool** | A function the agent can ask to run, such as "find flights" | `briefing/mcp_app.py` |

A **tool** is a function the agent can ask to run. The agent does not read flight data itself. It asks a tool, and the tool returns the answer.

## Get to the folder

Set `PACK` to the folder you cloned or unzipped, then go to the ready folder from Chapter 0:

```bash
export PACK=/absolute/path/to/software-factories-masterclass
cd "$PACK/book/ready/ch00/demo"
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

It lists the agent, the skill and the tool, then prints `ch01 OK`. If a file is missing, you are in the wrong folder or Chapter 0's ready folder is incomplete. Run the `cd` command above again.

## What you just learned

A Rasa Mantle agent is a folder of plain files: who the assistant is, what it should do, and which tools it can call. The cards come from the tool, never from the agent's own words.

Next: [Chapter 2](02-cards-from-real-sources.md) shows where the cards get their data.
