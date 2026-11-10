# A checked JSON handoff between the crew and the conversation

This small standard-library package starts the fixed CrewAI worker with a JSON
request on stdin and validates its JSON response. Rasa and CrewAI use separate
locked Python environments. The selected releases require different PyJWT
versions, so each runtime keeps its own dependency set.

Customer text travels as data. The worker command and interpreter are application
configuration. An accepted checklist must match the selected public source,
revision and document list. Worker errors, malformed responses and a timeout
return an incomplete result to the conversation. The subprocess has a 25-second
timeout; the Mantle tool allows 30 seconds.

Run the protocol controls from the Mantle project's `make test` after starting
both selected environments. The two native worker controls launch the actual
Crew executor with scripted model responses. The other controls check the JSON
contract, fixed command and failure handling.
