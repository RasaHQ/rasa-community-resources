# Words you will meet

You do not need to read this before the session. Keep it open in your codespace for the words that appear on the way. Each one is shown on the router restart helper you build.

| Word | What it means here |
|---|---|
| Codespace | A computer in your browser, made from this repository. Nothing is installed on your laptop. |
| Secret | A key you save in your GitHub account, such as `RASA_LICENSE` and `OPENAI_API_KEY`. The codespace reads it. You never paste it into a file or a chat. |
| Agent | A language model plus instructions, a conversation, and tools it may call. The router helper is one. |
| Rasa Mantle | The framework that runs the helper: it keeps the conversation, picks a skill, and calls its tool. |
| Skill | A focused set of instructions and tools for one job, here restarting a router. |
| Tool | A function the helper may call. The restart tool records one command, `REBOOT`. It contacts no router. |
| Inspector | The page where you chat with your helper and see what it did. |
| Source-file check | A script that reads the command written in the tool file. It does not watch a conversation. |
| Builder | A second agent, made with the OpenAI Agents API, that writes and saves one small file. It is told not to run it. |
| Tool server | A small program that hands your request to the builder and returns the result to the helper. |
| Fixture build | A practice build that copies a public sample and starts no Agents session. |
| sha256 | A short code made from a file's bytes. It shows that the file you checked is the file the builder saved. |
| Gate | A check the builder cannot edit. It judges the saved file without running it and says `ACCEPT` or `REJECT`. |
| Dark software factory | A line where agents do the work and checks they cannot edit decide what moves on. A person stands at a few defined gates. |

Follow `ATTENDEE-PACK.md` for the steps and `PARTICIPANT-GUIDE.md` for what to expect.
