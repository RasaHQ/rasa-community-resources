.PHONY: test data

test:
	python3 -B -m unittest discover -s tests -v

data:
	python3 -B fetch_data.py

.PHONY: audit-target
audit-target:
	python3 -B audit_target.py
