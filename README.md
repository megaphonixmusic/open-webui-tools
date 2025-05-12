# Various Open WebUI Tools by Megaphonix

**Current projects:**

* [YNAB API Request Tool](https://openwebui.com/t/megaphonix/ynab_api_request): Retrieves user's financial information (accounts or transactions) from YNAB API for LLM context
* [Actual API Request Tool](https://openwebui.com/t/megaphonix/actual_api_request): Same as above, but for [Actual Budget](https://actualbudget.com)

# Background

> [!WARNING]
> IMPORTANT: IT IS HIGHLY RECOMMENDED TO ONLY RUN THIS TOOL WITH LOCAL, PRIVATE LLMS, due to handling sensitive financial data and information

This Open WebUI tool is designed to plug in to [YNAB (YouNeedABudget)](https://www.ynab.com) or [Actual Budget](https://actualbudget.com) and enable the user to query their financial accounts and transactions by passing data as context to the LLM. It features auto-selection logic for the LLM to determine whether to query `accounts` or `transactions`, depending on the request, to minimize context token size to only what is necessary (future optimizations to come; see [TODO](#TODO)).

# How to install:

* Option 1: "One-click" install from [Open WebUI Community](https://openwebui.com/u/megaphonix)
* Option 2: Create a new Tool in Open WebUI -> Workspace -> Tools, then copy/paste the source code from the corresponding .py file in the GitHub repository

**YNAB Users:**
1. The first step is to set up a [Personal Access Token](https://api.ynab.com/#personal-access-tokens) via YNAB. Paste this into a text document - you'll need it later.
2. Next, [retrieve your Budget ID](https://api.ynab.com/#access-token-usage):
    * In a terminal window, execute the following command:
        * `curl https://api.ynab.com/v1/budgets?access_token=<ACCESS_TOKEN>`
    * You should see a response from YNAB with your Budget info (example below). Look for the corresponding "id" value(s) and paste this into the text document - you'll need this as well.
        * `"data": {
          "budgets ": [
            {"id": "cee64af3-a3df-425e-a18a-980e7ec10dc2", ...},
            {"id": "55697d98-b942-4f29-97d8-f870edd001d6", ...}
          ]
        }
         `

3. After setting up the Tool in Open WebUI, head into the Valves (user settings) and copy/paste the Access Token and Budget ID into the corresponding fields.

**Actual Users:**
1. After setting up the Tool in Open WebUI, head into the Valves (user settings):
    * *Base URL*: Where your Actual instance is located.
        * If you're running Open WebUI and Actual on the same machine, this is likely `http://localhost:<PORT>` (default port is 5006)
        * If you're running Open WebUI and Actual on different machines in the same network, this is likely `http://<ACTUAL_INSTANCE_IP_ADDRESS>:<PORT>`
        * If you're running Actual remotely (cloud server, etc.), the above *might* work, but please note this is untested.
     * *Password*: The password to your Actual file, that you use to log in to Actual.
     * (optional) *Encryption Password*: The encryption password for the file, if set.
     * *File (Budget) Name*: The exact name of the Budget (or 'file') to query.

# Changelog

v0.2.0 [2025-05-07]
* Refactored code
* Added Valves for:
    * 'Currency' (currently unusted) [Actual only]
    * 'Context Format'
    * 'Debug'

# TODO

* **Common:**
  - [ ] IMPORTANT: Add support and better handling for edge-case transactions, like Starting Balance, Transfer, etc.
  - [ ] Comment and clean up code for clarity and readability
  - [ ] Look into local cached data with persistent sync tracking, to reduce context size from API response and increase responsiveness
    - [ ] With local/persistent sync tracking, possibly implement account balance changes over time, such as "how much has my net worth changed over the past month"?
  - [ ] Incorporate more logic branches for transaction data parsing efficiency **<- Actual: probably easiest to use existing `actualpy` methods directly**
    - [ ] i.e. phrases in the user's query like "last week's purchases" or "last month's total spend on `<category>`" should probably trigger a method to filter by date range
  - [ ] Update system prompt to ask the LLM to provide ISO date formats alongside endpoint choice
    - [ ] i.e. dict: `{endpoint: "transactions", date_start: "2025-04-01", date_end: "2025-04-20"}`

* **YNAB API Request Tool:**
  - [ ] Incorporate [delta requests](https://api.ynab.com/#deltas)
  - [ ] Improve citations (Potentially deeplink to YNAB if possible?)
  - [x] ~~Reformat context into simple JSON for more accurate interpretation~~
    - [x] ~~Implement functions for JSONify, Markdownify, Plaintextify, and present it as a Valve for the user to select how the data is presented in the LLM context. Pros and cons for each.~~

* **Actual API Request Tool:**
  - [ ] Improve citations (Potentially deeplink to Actual if possible? Would need to have user specify if Actual query address is different from accessible address. For example: OWUI + Actual running on same machine would be `localhost:port`, but if OWUI accessed from another machine, would need to resolve citation URL differently)
  - [ ] Implement currency configuration
    - [ ] Actual is currency-agnostic, so this would be purely for presentation
  - [x] ~~Reformat context into simple JSON for more accurate interpretation~~
    - [x] ~~Implement functions for JSONify, Markdownify, Plaintextify, and present it as a Valve for the user to select how the data is presented in the LLM context. Pros and cons for each.~~
