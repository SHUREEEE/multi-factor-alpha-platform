.PHONY: install test backtest attribution v4-report v4-go-no-go clean

PYTHON ?= python

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest

backtest:
	$(PYTHON) scripts/run_backtest.py --weights results/pillar5_artifacts/v3_weights.parquet --prices data/processed/prices.parquet --output results/backtest

attribution:
	$(PYTHON) scripts/run_attribution.py

v4-report:
	$(PYTHON) scripts/run_v4_reports.py

v4-go-no-go:
	$(PYTHON) scripts/check_v4_launch_go_no_go.py

clean:
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; shutil.rmtree('.pytest_cache', ignore_errors=True)"
