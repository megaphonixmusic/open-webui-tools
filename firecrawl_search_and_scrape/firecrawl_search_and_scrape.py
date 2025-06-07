"""
title: Firecrawl Search And Scrape
description: Search with SearXNG and scrape with Firecrawl
author: megaphonix
author_url: https://github.com/megaphonixmusic
git_url: https://github.com/megaphonixmusic/open-webui-tools
required_open_webui_version: 0.6.5
requirements: tiktoken
version: 0.1.0
"""

# v0.0.1 [2025-06-06]
# - First commit

from datetime import datetime
from typing import Any, Callable, List, Optional, Literal, Awaitable
from pydantic import BaseModel, Field
import requests
import re
import json
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion

def clean_markdown(md):
    # Remove images and links, keep the text
    md = re.sub(r'!?\[([^\]]+)\]\([^\)]+\)', r'\1', md)
    # Remove empty link brackets left over
    md = re.sub(r'\[\]\([^\)]+\)', '', md)
    return md.strip()

class EventEmitter:

    def __init__(self, event_emitter: Callable[[dict], Any] = None):
        self.event_emitter = event_emitter

    async def emit(
        self,
        description="Unknown State",
        status="in_progress",
        done=False,
        err=None,
        debug="Off",
    ):
        if debug in {"Basic", "Full"}:
            debugMsg = f"[firecrawl_search_and_scrape] {status}: {description}"
            if not err == None:
                debugMsg += f" (Error: {err})"
            print(debugMsg)
        if self.event_emitter:
            await self.event_emitter(
                {
                    "type": "status",
                    "data": {
                        "status": status,
                        "description": description,
                        "done": done,
                    },
                }
            )


class Tools:
   
    class Valves(BaseModel):

        FIRECRAWL_BASE_URL: str = Field(
            default="https://api.firecrawl.dev/v1",
            title="Firecrawl Base URL",
            description="Can be cloud-hosted (default) or locally-hosted (i.e. http://localhost:3002/v1). Cloud-hosted requires API key. URL must end in /v1",
            required=True
        )
        FIRECRAWL_API_KEY: str = Field(
            default="",
            title="Firecrawl API Key",
            description="(Optional) Not needed if running locally",
            required=False
        )
        SEARXNG_BASE_URL: str = Field(
            default="",
            title="SearXNG Base URL",
            description="Example: http://localhost:8080",
            required=True
        )
        NUMBER_OF_RESULTS: int = Field(
            default=5,
            title="Number of Results",
            description="Number of search results to scrape",
            required=True
        )
        DEBUG: Literal["Off", "Basic", "Full"] = Field(
            default="Off",
            description="Toggle verbose debugging in OpenWebUI logs. Off = none, Basic = status messages, Full = includes raw data",
            required=False,
        )
        CITATIONS: bool = Field(
            default=False,
            description="Enables in-line citations",
            required=False,
        )
        TIMEOUT: int = Field(
            default=30,
            description="Request timeout in seconds",
            required=False
        )
        pass

    def __init__(self):
        self.valves = self.Valves()
        self.citation = self.valves.CITATIONS

    async def _run(
        self,
        query: str,
        __event_emitter__: Callable[[Any], Awaitable[None]],
        __request__: Any,
        __user__: Optional[dict] = None,
        __model__: Optional[dict] = None,
    ) -> str:
        """
        Initiates a web search with SearXNG, scrapes the results with Firecrawl, and returns all content in a JSON structure with Markdown page contents.

        :param query: The query to search
        :return: The scraped content in JSON with Markdown page contents
        """
        emitter = EventEmitter(__event_emitter__)
        debugState = self.valves.DEBUG

        await emitter.emit(
            description="Generating search query...", debug=debugState
        )

        system_prompt = f"""
            You are tasked with generating a distilled and relevant web search query from the user's input query, optimized for maximum accuracy and efficacy with search engines.\n
            You must respond only with the query in plain text, and nothing else.\n
            Example: "What's the weather in San Francisco right now?" -> "San Francisco weather"
            """

        prompt = f"User's prompt: {query}"

        queryPayload = {
            "model": __model__.get("id") if isinstance(__model__, dict) else __model__,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }

        try:
            user = Users.get_user_by_id(__user__["id"])
            response = await generate_chat_completion(
                request=__request__, form_data=queryPayload, user=user
            )
            searchQuery = response["choices"][0]["message"]["content"]
            searchQuery = searchQuery.replace("'", '"')
        except Exception as e:
            searchQueryError = (
                "Error occurred while generating search query"
            )
            await emitter.emit(
                status="error",
                description=f"{searchQueryError} {e}",
                done=True,
                err=e,
                debug=debugState,
            )
            return searchQueryError







        try:

            await emitter.emit(
                description=f"Searching the web for \"{searchQuery}\"...", debug=debugState
            )

            firecrawlPayload = {
                "limit": self.valves.NUMBER_OF_RESULTS,
                "scrapeOptions": {
                    "formats": [
                        "markdown"
                    ]
                },
                "query": searchQuery,
                "timeout": self.valves.TIMEOUT*1000
            }

            # Make the request
            url = f"{self.valves.FIRECRAWL_BASE_URL}/search"

            headers = {"Content-Type": "application/json"}
            if self.valves.FIRECRAWL_API_KEY:
                headers["Authorization"] = f"Bearer {self.valves.FIRECRAWL_API_KEY}"

            response = requests.post(
                url,
                json=firecrawlPayload,
                headers=headers,
                timeout=self.valves.TIMEOUT*1000
            )

            if response.status_code != 200:
                scrapeError = f"Error: Failed to scrape URL. Status code: {response.status_code} - payload send: {firecrawlPayload}"
                await emitter.emit(
                    status="error",
                    description=f"{scrapeError}",
                    done=True,
                    err=None,
                    debug=debugState,
                )
                return scrapeError

            # Parse the response
            response_data = response.json()

            if not response_data.get("success"):
                responseError = (
                    f"Error: {response_data.get('error', 'Unknown error occurred')}"
                )
                await emitter.emit(
                    status="error",
                    description=f"{responseError}",
                    done=True,
                    err=None,
                    debug=debugState,
                )
                return responseError

            # Return the content
            # print("URL: " + str(url))
            data = response_data.get("data")
            content = []
            for result in data:
                resultTitle = result.get("title")
                resultUrl = result.get("url")
                resultMarkdown = clean_markdown(result.get("markdown"))
                content.append(f"## Source: [{resultTitle}]({url})\n\n{resultMarkdown}")

            content = "\n\n---\n\n".join(content)

            # Success message
            await emitter.emit(
                description=f"Firecrawl successfully scraped content",
                debug=debugState,
                status="complete",
                done=True
            )

            return content

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            await emitter.emit(
                    status="error",
                    description=f"{error_msg} {e}",
                    done=True,
                    err=e,
                    debug=debugState,
                )
            return error_msg
