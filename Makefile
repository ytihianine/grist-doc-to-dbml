# ==================================
# Variables
# ==================================
ENV_NAME = env

# OS detection
ifeq ($(OS),Windows_NT)
    PYTHON := python
    VENV_BIN := $(ENV_NAME)/Scripts
else
    PYTHON := python3
    VENV_BIN := $(ENV_NAME)/bin
endif

.PHONY: create-py-env clean install-py-packages install-pre-commit test run-pre-commit

# ==================================
# Developpement Environment Setup
# ==================================
create-py-env: ## Créer un nouvel environnement python
	@echo "Création d'un environnement"
	$(PYTHON) -m venv $(ENV_NAME)
	@echo "L'environnement a été créé"
	@echo "Activation du nouvel environnement"
	@echo "Exécuter dans votre terminal: source $(ENV_NAME)/bin/activate"

install-py-packages: ## Installer les packages python
	@echo "Installation/Mise à jour de pip"
	$(VENV_BIN)/python -m pip install --upgrade pip
	@echo "Installation de uv"
	$(VENV_BIN)/python -m pip install uv
	@echo "Installation des packages requis"
	$(VENV_BIN)/uv pip install \
		--python $(VENV_BIN)/python \
		--group default \
		--group dev

install-pre-commit: ## Installer pre-commit
	$(VENV_BIN)/pre-commit install

setup-dev-env: create-py-env install-py-packages install-pre-commit ## Configurer l'environnement de développement

run-pre-commit: ## Lancer pre-commit
	$(VENV_BIN)/pre-commit run --all-files

# ==================================
# Clean-up
# ==================================

clean: ## Nettoie les fichiers temporaires
	@echo "Nettoyage des fichiers temporaires"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "✓ Nettoyage terminé"
