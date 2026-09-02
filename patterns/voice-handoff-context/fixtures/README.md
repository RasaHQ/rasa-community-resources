# fixtures/

`desk_queue/` is where the running agent delivers context packages, and where
`scripts/agent_desk.py <file>` reads them back from. It is gitignored: the files
are runtime output containing real conversation state.

The directory stands in for a contact-centre queue. Swapping it for a real one
means replacing `deliver()` in `handoffpkg/desk.py` and nothing else — see that
function's docstring, and the tutorial section "Where a real integration
attaches".
