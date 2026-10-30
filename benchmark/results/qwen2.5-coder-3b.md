# Benchmark: qwen2.5-coder:3b

**Solved 6 of 18** (33%), judged by hidden tests the agent never saw.

| Metric | Value |
|---|---|
| Solved | 6 / 18 |
| Offered for review (agent's own tests passed) | 8 |
| Of those, also passed the hidden test | 75% |
| Solved on the first attempt / after a retry | 5 / 1 |
| Wrote a regression test that failed before the fix | 12 / 18 |
| Median agent time per issue | 204 s |
| Total agent time | 72.3 min |

| # | Issue | Result | Attempts | Regression test | Time | Note |
|---|---|---|---|---|---|---|
| 1 | slugify leaves double dashes in URLs | solved | 1 | yes | 100 s |  |
| 2 | truncate returns text longer than the limit | wrong fix | 1 | no | 130 s | Hidden test failed: 1 failed, 14 passed in 0.33s |
| 3 | Prices with single-digit cents display wrong | failed | 3 | yes | 200 s | No patch passed after 3 attempts. Last problem: The 'find' text was not found in shopkit/money.py. Copy it exactly from the file, including indentation. |
| 4 | Discount over 100% makes the price negative | failed | 3 | yes | 473 s | No patch passed after 3 attempts. Last problem: The 'find' text was not found in shopkit/cart.py. Copy it exactly from the file, including indentation. |
| 5 | Adding the same item twice loses the first quantity | solved | 1 | no | 203 s |  |
| 6 | Bulk discount not applied at exactly 10 items | failed | 3 | yes | 385 s | 1 failed, 14 passed in 0.35s |
| 7 | Saturday is treated as a working day | solved | 2 | yes | 158 s |  |
| 8 | median is wrong for an even number of values | failed | 3 | yes | 150 s | 1 failed, 14 passed in 0.40s |
| 9 | Product descriptions keep tabs and line breaks | failed | 3 | no | 626 s | Tests did not finish within 120s. |
| 10 | Prices with a thousands separator crash the import | failed | 3 | yes | 239 s | No patch passed after 3 attempts. Last problem: The 'find' text was not found in shopkit/money.py. Copy it exactly from the file, including indentation. |
| 11 | Splitting a bill loses a cent | failed | 3 | yes | 206 s | No patch passed after 3 attempts. Last problem: The 'find' text was not found in shopkit/money.py. Copy it exactly from the file, including indentation. |
| 12 | Invoice dates are read with day and month swapped | failed | 3 | yes | 214 s | No patch passed after 3 attempts. Last problem: The 'find' text was not found in shopkit/dates.py. Copy it exactly from the file, including indentation. |
| 13 | Sales growth percentage is wrong | solved | 1 | yes | 154 s |  |
| 14 | Best sellers list shows the worst sellers | failed | 3 | yes | 287 s | 1 failed, 14 passed in 0.47s |
| 15 | Stock goes negative when an order is bigger than the stock | wrong fix | 2 | no | 205 s | Hidden test failed: 1 failed, 14 passed in 0.47s |
| 16 | Low-stock report misses items exactly at the threshold | solved | 1 | no | 161 s |  |
| 17 | Every order gets free shipping | solved | 1 | no | 191 s |  |
| 18 | Removing an item that is not in the cart crashes | failed | 3 | yes | 254 s | 1 failed, 13 passed, 1 error in 0.52s |
