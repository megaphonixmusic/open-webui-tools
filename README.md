# Various Open WebUI Tools by Megaphonix

**Current projects:**

* [YNAB API Request Tool](https://openwebui.com/t/megaphonix/ynab_api_request): Retrieves user's financial information (accounts or transactions) from YNAB API for LLM context
* [Actual API Request Tool](https://openwebui.com/t/megaphonix/actual_api_request): Same as above, but for [Actual Budget](https://actualbudget.com)

# TODO

* **YNAB API Request Tool:**
  - [ ] Refactor and comment code for clarity and readability
  - [ ] Reformat context into Markdown for easier interpretation
  - [ ] Incorporate [delta requests](https://api.ynab.com/#deltas) or local cached data with persistent sync tracking, to reduce context size from API response and increase responsiveness
    - [ ] With local/persistent sync tracking, possibly implement account balance changes over time, such as "how much has my net worth changed over the past month"?
  - [ ] Incorporate more logic branches for transaction data parsing efficiency
    - [ ] i.e. phrases in the user's query like "last week's purchases" or "last month's total spend on `<category>`" should probably trigger a method to filter by date range
  - [ ] Update system prompt to ask the LLM to provide ISO date formats alongside endpoint choice
    - [ ] i.e. `[endpoint: "transactions", date_start: "2025-04-01", date_end: "2025-04-20"]`

* **Actual API Request Tool:**
  - [ ] Refactor and comment code for clarity and readability
  - [x] Reformat context into Markdown for easier interpretation
  - [ ] Incorporate [delta requests](https://api.ynab.com/#deltas) or local cached data with persistent sync tracking, to reduce context size from API response and increase responsiveness
    - [ ] With local/persistent sync tracking, possibly implement account balance changes over time, such as "how much has my net worth changed over the past month"?
  - [ ] Incorporate more logic branches for transaction data parsing efficiency **<- Probably easiest to use existing `actualpy` methods directly**
    - [ ] i.e. phrases in the user's query like "last week's purchases" or "last month's total spend on `<category>`" should probably trigger a method to filter by date range
  - [ ] Update system prompt to ask the LLM to provide ISO date formats alongside endpoint choice
    - [ ] i.e. dict: `{endpoint: "transactions", date_start: "2025-04-01", date_end: "2025-04-20"}`
