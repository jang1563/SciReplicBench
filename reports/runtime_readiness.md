# Runtime Readiness

| Check | Status | Detail |
|---|---|---|
| python | ok | Detected Python 3.11.2 (requires >= 3.11) |
| import:inspect_ai | ok | Module 'inspect_ai' import OK |
| command:docker | ok | /usr/local/bin/docker |
| docker_engine | blocked | permission denied while trying to connect to the docker API at unix:///Users/jak4013/.docker/run/docker.sock |
| file:environments/compose.yaml | ok | environments/compose.yaml |
| file:src/scireplicbench/tasks.py | ok | src/scireplicbench/tasks.py |
| env:OPENAI_API_KEY | ok | available via /Users/jak4013/.api_keys |
| env:ANTHROPIC_API_KEY | ok | available via /Users/jak4013/.api_keys |
| env:DEEPSEEK_API_KEY | ok | available via /Users/jak4013/.api_keys |
