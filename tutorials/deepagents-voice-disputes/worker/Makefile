install:
	uv sync --locked --python 3.12
test:
	uv run --locked python -B -m unittest discover -s ../tests -p 'test_worker_native.py' -v
