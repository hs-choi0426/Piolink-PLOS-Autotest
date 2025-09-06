VENV_NAME := .venv
PYTHON := $(VENV_NAME)/bin/python
PIP := $(VENV_NAME)/bin/pip

PACKAGES := requirements.txt

.PHONY: all
all: install

$(VENV_NAME):
	python3 -m venv $(VENV_NAME)

install: $(VENV_NAME)
	$(PIP) install -r $(PACKAGES)

.PHONY: clean
clean: clean-pyc
	rm -rf $(VENV_NAME)

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +
	find . -name 'current_log' -exec rm -fr {} +
	rm -rf backup/*

