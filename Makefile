#
# Makefile
# Karol Będkowski, 2016-11-26 16:11
#

.PHONY: run
## Run application
run:
	./run_webmon2.py -d -c webmon2.ini serve --workers 1

.PHONY: pylint
## Lint using pylint
pylint:
	pylint webmon2 | tee pylint.txt

.PHONY: mypy
## Lint using mypy
mypy:
	mypy webmon2 | tee mypy.txt

.PHONY: check
## Lint using ruff
check:
	ruff .

.PHONY: clean
## Delete all temporary files
clean:
	rm -rf .ipynb_checkpoints
	rm -rf **/.ipynb_checkpoints
	rm -rf .pytest_cache
	rm -rf **/.pytest_cache
	rm -rf __pycache__
	rm -rf **/__pycache__
	rm -rf build
	rm -rf dist
	rm -f report_*.txt report_*.html webmon_*.prom
	rm -f pylint.txt mypy.txt
	rm -fr htmlcov/

.PHONY: format
## Format files using black & isort
format:
	ruff . --fix
	black .

.PHONY: test
## Run tests
test:
	pytest --cov=webmon2 --cov-report=html --log-level=WARNING --disable-pytest-warnings

.PHONY: pot
## Generate pot files
pot:
	pybabel extract -F babel.cfg -k _ -k lazy_gettext -o messages.pot .

.PHONY: po
## Update po files
po:
	pybabel update -i messages.pot -d webmon2/translations

.PHONY: mo
## Generaate translations
mo:
	pybabel compile -d webmon2/translations

.PHONY: build
## build packages
build: clean
	pip-compile --generate-hashes \
		--extra=sdnotify --extra=minify --extra=otp \
		--output-file=requirements-extra.txt pyproject.toml
	pip-compile --generate-hashes --extra=dev --output-file=requirements-dev.txt pyproject.toml
	pip-compile --generate-hashes --output-file=requirements.txt pyproject.toml
	hatchling build


#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

# Inspired by <http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html>
# sed script explained:
# /^##/:
# 	* save line in hold space
# 	* purge line
# 	* Loop:
# 		* append newline + line to hold space
# 		* go to next line
# 		* if line starts with doc comment, strip comment character off and loop
# 	* remove target prerequisites
# 	* append hold space (+ newline) to line
# 	* replace newline plus comments by `---`
# 	* print line
# Separate expressions are necessary because labels cannot be delimited by
# semicolon; see <http://stackoverflow.com/a/11799865/1968>
.PHONY: help
help:
	@echo "$$(tput bold)Available commands:$$(tput sgr0)"
	@sed -n -e "/^## / { \
		h; \
		s/.*//; \
		:doc" \
		-e "H; \
		n; \
		s/^## //; \
		t doc" \
		-e "s/:.*//; \
		G; \
		s/\\n## /---/; \
		s/\\n/ /g; \
		p; \
	}" ${MAKEFILE_LIST} \
	| awk -F '---' \
		-v ncol=$$(tput cols) \
		-v indent=19 \
		-v col_on="$$(tput setaf 6)" \
		-v col_off="$$(tput sgr0)" \
	'{ \
		printf "%s%*s%s ", col_on, -indent, $$1, col_off; \
		n = split($$2, words, " "); \
		line_length = ncol - indent; \
		for (i = 1; i <= n; i++) { \
			line_length -= length(words[i]) + 1; \
			if (line_length <= 0) { \
				line_length = ncol - indent - length(words[i]) - 1; \
				printf "\n%*s ", -indent, " "; \
			} \
			printf "%s ", words[i]; \
		} \
		printf "\n"; \
	}'

# vim:ft=make
