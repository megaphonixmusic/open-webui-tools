"""
title: YNAB API Request
description: Retrieves user's financial information (accounts or transactions) from YNAB API to answer personal finance questions
author: megaphonix
author_url: https://github.com/megaphonixmusic
version: 0.1.1
required_open_webui_version: 0.6.5
"""

# !!! IMPORTANT: IT IS HIGHLY RECOMMENDED TO ONLY RUN THIS TOOL WITH LOCAL, PRIVATE LLMS !!!
# (Due to handling sensitive financial data and information)
#
# How to retrieve your personal YNAB API token: https://api.ynab.com/#personal-access-tokens
#
# How to retrieve your Budget ID:
#     Step 1: https://api.ynab.com/#access-token-usage
#     Step 2: https://api.ynab.com/#response-format

from datetime import datetime, timedelta
from typing import List, Dict, Callable, Any, Optional, Awaitable
from pydantic import BaseModel, Field
import requests
import re
import json
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion

class Tools:

    class Valves(BaseModel):
        ynab_budget_id: str = Field(
            default="",
            description="Budget ID to query. Can be obtained with YNAB API (see README)",
            required=True,
        )
        ynab_access_token: str = Field(
            default="", description="YNAB API authorization token", required=True
        )
        debug: bool = Field(
            default=False, description="Enables verbose debugging in OpenWebUI logs"
        )
        citations: bool = Field(
            default=False, description="Enables in-line 'citations', proving response is sourced from actual YNAB data. Looks messy, but is useful for debugging/differentiating from hallucinations"
        )
        pass

    def __init__(self):
        self.valves = self.Valves()
        self.citation = False
        if self.valves.debug:
            print("ynab_api_request: init")
        pass

    async def _run(
        self,
        query: str,
        __event_emitter__: Callable[[Any], Awaitable[None]],
        __request__: Any,
        __user__: Optional[dict] = None,
        __model__: Optional[dict] = None,
    ) -> str:

        def format_currency(amount: float) -> str:
            if amount < 0:
                return f"-${abs(amount):,.2f}"
            else:
                return f"${amount:,.2f}"

        budget_id = self.valves.ynab_budget_id
        access_token = self.valves.ynab_access_token
        headers = {"Authorization": f"Bearer {access_token}"}

        if self.valves.debug:
            print(f"ynab_api_request: determining which YNAB data to retrieve")
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": "Determining which YNAB data to retrieve...",
                    "done": False,
                },
            }
        )

        # Use LLM to decide which API endpoint to call
        tools_metadata = [
            {
                "id": "accounts",
                "description": "Retrieve a list of all account and balance details from YNAB.",
            },
            {
                "id": "transactions",
                "description": "Retrieve a list of all financial transaction details from YNAB.",
            },
        ]

        system_prompt = (
            """You are an assistant tasked with retrieving financial data for the user through 'YNAB' (aka You Need A Budget), a financial tracking and budgeting app.
            Do not rely on fake financial data in your own knowledge base;
            instead, determine the best tool below that will be used to query for the user's real YNAB data pertaining to the user's request."""
            + "\nTools: " + str(tools_metadata)
            + "\nIf a tool doesn't match the query, return an empty list []. Otherwise, return a list of matching tool IDs in the format ['tool_id']. Only return the list. Do not return any other text."
            + "\nExamples of queries that fall under ['accounts'] include 'What is my net worth?', 'How much is in my checking account?', 'How much do I owe on my student loans?', 'How much debt do I have?'"
            + "\nExamples of queries that fall under ['transactions'] include 'How much total did I spend last week?', 'How many times did I get Starbucks last month?', 'What is my largest purchase year-to-date?'"
        )

        prompt = f"Query: {query}"

        # Trying to figure out how to get the global "keep_alive" setting... this doesn't work yet
        keep_alive = getattr(__request__.state, "keep_alive", None)
        print(f"keep_alive = {keep_alive}")

        payload = {
            "model": __model__.get("id") if isinstance(__model__, dict) else __model__,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "keep_alive": keep_alive,
            "stream": False
        }

        try:
            user = Users.get_user_by_id(__user__["id"])
            response = await generate_chat_completion(
                request=__request__, form_data=payload, user=user
            )
            content = response["choices"][0]["message"]["content"]
            content = content.replace("'", '"')
            match = re.search(r"\[.*?\]", content)
            endpoint = None
            if match:
                try:
                    tools = json.loads(match.group(0))
                    if isinstance(tools, list) and tools:
                        endpoint = tools[0]
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            if self.valves.debug:
                print(f"ynab_api_request: error deciding tool: {e}")
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Error deciding tool: {e}",
                        "done": True,
                    },
                }
            )
            return "Error occurred while determining what data to retrieve."

        if endpoint == "accounts":
            if self.valves.debug:
                print(f"ynab_api_request: fetching YNAB account data")
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Fetching YNAB account data",
                        "done": False,
                    },
                }
            )

            url = f"https://api.ynab.com/v1/budgets/{budget_id}/accounts"
            try:
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    if self.valves.debug:
                        print(f"ynab_api_request: YNAB API error: {response.status_code} {response.text}")
                    return f"YNAB API error: {response.status_code} {response.text}"
                accounts = response.json().get("data", {}).get("accounts", [])
                if not accounts:
                    if self.valves.debug:
                        print(f"ynab_api_request: no accounts found")
                    return "No accounts found."

                processed_accounts = []
                for acc in accounts:
                    if not acc.get("closed", False):
                        processed_accounts.append({
                            "name": acc.get("name"),
                            "balance": acc.get("balance", 0) / 1000.0,
                            "type": acc.get("type"),
                            "included_in_budget": acc.get("on_budget", False)
                        })

                if self.valves.debug:
                    print("ynab_api_request: YNAB account data fetched successfully")
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"YNAB account data fetched successfully",
                            "done": True,
                        },
                    }
                )

                return  {
                    "All YNAB Accounts": processed_accounts
                }
            except Exception as e:
                if self.valves.debug:
                    print(f"ynab_api_request: error fetching YNAB accounts: {str(e)}")
                return f"Error fetching YNAB accounts: {str(e)}"

        elif endpoint == "transactions":

            if self.valves.debug:
                    print(f"ynab_api_request: fetching YNAB transaction data")
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Fetching YNAB transaction data",
                        "done": False,
                    },
                }
            )

            url = f"https://api.ynab.com/v1/budgets/{budget_id}/transactions"
            try:
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    if self.valves.debug:
                        print(f"ynab_api_request: YNAB API error: {response.status_code} {response.text}")
                    return f"YNAB API error: {response.status_code} {response.text}"
                transactions = response.json().get("data", {}).get("transactions", [])
                if not transactions:
                    if self.valves.debug:
                        print("ynab_api_request: no transactions found")
                    return "No transactions found."

                processed_transactions = []
                for tx in transactions:
                    processed_transactions.append({
                        "date": tx.get("date", ""),
                        "payee": tx.get("payee_name", "Unknown"),
                        "amount": tx.get("amount", 0) / 1000.0,
                        "category": tx.get("category_name", "Uncategorized"),
                        "account": tx.get("account_name", "Unknown Account"),
                        "memo": tx.get("memo", ""),
                    })

                if self.valves.debug:
                        print("ynab_api_request: YNAB data fetched successfully")
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"YNAB transaction data fetched successfully",
                            "done": True,
                        },
                    }
                )

                return {
                    "All YNAB Transactions": processed_transactions
                }
            except Exception as e:
                if self.valves.debug:
                        print(f"ynab_api_request: error fetching YNAB transactions: {str(e)}")
                return f"Error fetching YNAB transactions: {str(e)}"

        if self.valves.debug:
            print(f"ynab_api_request: no matching YNAB data found")
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": "No matching YNAB data found.",
                    "done": True,
                },
            }
        )
        return "I'm not sure which YNAB data to retrieve based on your query."
