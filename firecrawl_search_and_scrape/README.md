# Firecrawl Search And Scrape by Megaphonix

* [Firecrawl Search And Scrape](https://openwebui.com/t/megaphonix/firecrawl_search_and_scrape): Search with SearXNG and scrape with Firecrawl (NOTE: Only tested on fully local setup)

# Background

> [!WARNING]
> This Tool has only been tested on my own fully localized setup, running Firecrawl and SearXNG in Docker containers. I may be missing steps or config specifics; I recommend checking [Firecrawl's Self-Hosting docs](https://docs.firecrawl.dev/contributing/self-host) for additional troubleshooting.
> Alternatively, you may be able to use remotely hosted instances, such as the official Firecrawl API endpoint, but **this functionality has not been tested**.

This Open WebUI tool is designed to plug in to [Firecrawl](https://www.firecrawl.dev) and enable the user to search the web with SearXNG and scrape the search results with Firecrawl, optimizing for LLM context.

# How to install:

* Option 1: "One-click" install from [Open WebUI Community](https://openwebui.com/u/megaphonix)
* Option 2: Create a new Tool in Open WebUI -> Workspace -> Tools, then copy/paste the source code from the corresponding .py file in the GitHub repository

**Setup:**
1. Set up Firecrawl:
    1. If self-hosting: Follow [Firecrawl's Self-Hosting docs](https://docs.firecrawl.dev/contributing/self-host) to get Firecrawl running locally in a Docker container and test its functionality/accessibility at the default address (http://localhost:3002/v1/search) in your terminal. **Make sure to configure your SearXNG URL in the `SEARXNG_ENDPOINT` environment variable in the firecrawl/docker-compose.yaml file before building the Docker container!**
    2. If using API: Set up an account at http://firecrawl.dev/ and grab your generated API key.
2. After confirming Firecrawl functionality, set the `Firecrawl Base URL` field to the appropriate address (depending on local or API), and set the `Firecrawl API Key` field to the API key (not applicable to local).
3. Tweak other Valves/settings as desired

# Changelog

v0.0.1 [2025-06-06]
* First commit

# TODO

* **Common:**
  - [ ] Comment and clean up code for clarity and readability
  - [ ] Further optimize scraped Markdown results for more efficient tokenization
  - [ ] Solve citations