# The image the agent's tests run in. Build it once:
#   docker build -t issue-agent-sandbox sandbox
FROM python:3.12-slim

RUN pip install --no-cache-dir "pytest>=8,<9"

# Tests run as an unprivileged user, never root.
RUN useradd --create-home --uid 1000 runner
USER runner
WORKDIR /work
