# The Anaconda `hydra` pytest plugin (unrelated to HydraDG) breaks pytest autoload on magicPRObox.
test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests -q -p no:cacheprovider
scan:
	gitleaks detect --no-git --source . --redact
