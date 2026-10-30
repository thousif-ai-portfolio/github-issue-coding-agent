# Video walkthrough: GitHub Issue Coding Agent (about 3 minutes)

> The recorded video is [`demo.mp4`](demo.mp4): real screenshots of a live run, narrated
> with the offline Windows voice. To re-record it in your own voice, follow the script below.

## Before you record

- **Start everything:** Docker Desktop and Ollama running, then
  `uvicorn agent.main:app` in the project folder, and open http://localhost:8000.
- **Warm up the model:** start one practice run first. The first model call after a break
  takes about a minute while the model loads.
- **Record a run ahead of time.** A run takes about 3 minutes on a laptop CPU. Start a
  run on **issue #8 (median)** about 5 minutes before recording, so a finished run is
  waiting at "Needs review". On camera, start a second run to show it working live, then
  switch to the finished one. Or cut the waiting out in editing.
- **Record** with the Xbox Game Bar (`Win + G`) or OBS at 1080p, browser zoomed to 125%.
- Open these tabs first: the dashboard, `benchmark/results/` on GitHub, and the GitHub repo.

---

## 1. The problem (0:00 - 0:15)

**Show:** the dashboard, with the run list on the left.

> "Coding agents write patches that look right but often aren't. I built one that has to
> prove its fix: it writes a test that reproduces the bug first, fixes the code, runs
> the tests in an isolated container, and then waits for a person to approve. It runs on
> my laptop with a small local model: no API keys, no cost."

## 2. Pick an issue (0:15 - 0:35)

**Do:** in New run, keep Demo repo, pick **#8 median is wrong for an even number of
values**, press **Start run**.

> "This is a demo shop library with 18 bugs I planted. Each has an issue written the way
> a user would report it, and a hidden test the agent never sees, which I use to grade
> it. I'll give it the median bug."

## 3. Watch it work (0:35 - 1:05)

**Show:** the step timeline filling in, with the live timer.

> "Every step is recorded. It classifies the issue, searches the code through an MCP tool
> server, and picks the files to change. Then the important part: it writes a regression
> test, and that test has to fail on the current code. If it passes, it doesn't prove
> the bug, so the agent tries again."

**Do:** click the **Write regression test** step to open it, and show the prompt.

> "Each step keeps its input and output, so I can see exactly what the model was asked."

## 4. Review the fix (1:05 - 1:50)

**Do:** switch to the finished run at "Needs review". Scroll slowly.

> "Here's a finished run. The fix: for an even count, average the two middle values.
> Here's the test the agent wrote, which failed before the fix. And here's the test
> output from the Docker sandbox: no network, read-only, unprivileged user, memory and
> CPU limits. If the tests had failed, the output would go back to the model, up to
> three tries."

**Do:** type a short comment, click **Approve**.

> "Nothing reaches GitHub without a person. For a real repository, approving opens a
> draft pull request from the exact commit that was tested. For the demo repo, it saves
> the patch."

## 5. Honest results (1:50 - 2:35)

**Show:** `benchmark/results/` (the .md file) on GitHub, or the Results section of the README.

> "I benchmarked it on all 18 issues, graded by the hidden tests. With a 3-billion-
> parameter model on a laptop, it fixes 6 of 18. The more useful number: when its own
> tests pass and it asks for review, it's right 75 percent of the time. The benchmark
> also caught a bug in my agent: at first it never managed to write a regression test.
> Fixing that cut the wrong fixes reaching review from 6 to 2. Most remaining failures
> are the small model failing to copy code exactly, which is why a person approves
> every patch, and why a bigger model is a one-line config change."

## 6. How it's built (2:35 - 3:00)

**Show:** the README's flowchart, then the GitHub Actions page with green checks.

> "It's a LangGraph state machine with SQLite checkpoints, so a run waiting for review
> survives a restart. Tools go through an MCP server, the API is FastAPI, the dashboard
> is React. CI runs the tests, including the Docker sandbox tests, on every push.
> The code is on GitHub. Thanks for watching."

---

## After recording

- Trim the waits, add captions if you like, and keep it under 3 minutes.
- Upload to YouTube as **Unlisted** (or Loom), and put the link at the top of the README.
