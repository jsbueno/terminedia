.PHONY: clean-build clean-pyc clean-test clean lint coverage test

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +
	find . -name 'terminedia-*.dist-info' -exec rm -fr {} +

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test:
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache

clean: clean-build clean-pyc clean-test

install: clean
	poetry install -vvv

update-deps: clean
	poetry update
	poetry install -vvv

lint:
	poetry run flake8 terminedia

coverage: lint
	poetry run pytest --cov=terminedia --cov-fail-under=10

test: lint
	poetry run pytest

dev-env-setup:
	cd
	git clone git://github.com/yyuu/pyenv.git .pyenv
	echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
	echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
	echo 'eval "$(pyenv init -)"' >> ~/.bashrc
	source ~/.bashrc
	# installs poetry isolated from other python envs
	curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python
	# install pyenv to manage an isolated dev environemtn
	curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash
	# minimal python environment for terminedia
	pyenv install 3.6.8
	# install pyenv to easily manage dev environment
	git clone https://github.com/yyuu/pyenv-virtualenv.git ~/.pyenv/plugins/pyenv-virtualenv
	source ~/.bashrc
	# create virtualenv for terminedia development environment and activate it
	pyenv virtualenv 3.6.8 terminedia-dev-env
	pyenv activate terminedia-dev-env
	# checks python current version: should print $HOME/.pyenv/shims/python
	which python

publish:
	poetry build
	poetry publish --username ${username} --password ${password}

jump-start: dev-env-setup install
	# If the installation was successfull, it should print the
	terminedia-bezier
