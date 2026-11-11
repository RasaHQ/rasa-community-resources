.PHONY: test

# Native runtime/transport controls use only loopback fixtures and scripted
# model responses. The tests bind their own placeholders, never real keys.
test:
	uv run --locked python -m unittest discover -s . -p 'test_*.py' -v
