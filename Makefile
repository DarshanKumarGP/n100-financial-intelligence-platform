# N100 Financial Intelligence Platform - Makefile
# If 'make' isn't available on your system, run the commands on the
# right-hand side of each target directly instead.

load:
	python src/etl/loader.py

ratios:
	python src/analytics/ratios.py

test:
	pytest tests/ --html=reports/pytest_report.html --self-contained-html

report:
	python src/reports/portfolio_report.py

dashboard:
	streamlit run src/dashboard/app.py

api:
	uvicorn src.api.main:app --port 8000

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
