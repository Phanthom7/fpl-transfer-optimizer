PY ?= python
PHASE ?=

.PHONY: test evals ingest data

test:
	$(PY) -m pytest -q tests --ignore=tests/evals

evals:
ifeq ($(PHASE),)
	$(PY) -m pytest -q tests/evals; $(PY) -m evals.report
else
	$(PY) -m pytest -q tests/evals/test_phase$(PHASE)_*.py; $(PY) -m evals.report $(PHASE)
endif

ingest:
	$(PY) -m src.ingest.run

data:
	$(PY) -m src.ingest.run
	$(PY) -m src.clean.run
	$(PY) -m src.features.run
