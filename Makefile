.DEFAULT_GOAL := help
SYSTEM_PYTHON := /usr/bin/python3

.PHONY: help setup setup-python install-cron remove-cron cron-status run test

help:
	@echo "make setup        Set up system Python/GNOME dependencies and the user cron job"
	@echo "make setup-python Install/check Python and PyGObject only"
	@echo "make install-cron Install/update the every-minute cron job for this checkout"
	@echo "make remove-cron  Remove this tool's cron job, preserving unrelated jobs"
	@echo "make cron-status  Show the configured wake job"
	@echo "make run          Wake the current GNOME desktop once"
	@echo "make test         Run isolated unit tests"

setup:
	bash setup.sh

setup-python:
	bash setup.sh python

install-cron:
	bash setup.sh cron

remove-cron:
	$(SYSTEM_PYTHON) manage_cron.py remove

cron-status:
	$(SYSTEM_PYTHON) manage_cron.py status

run:
	$(SYSTEM_PYTHON) wake.py

test:
	$(SYSTEM_PYTHON) -B -m unittest discover -s . -p 'test_*.py' -v
