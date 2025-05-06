"""
title: Actual API Request
description: Retrieves user's financial information (accounts or transactions) from Actual API to answer personal finance questions
author: megaphonix
author_url: https://github.com/megaphonixmusic
version: 0.1.0
required_open_webui_version: 0.6.5
requirements: actualpy>=0.12.1
"""

# !!! IMPORTANT: IT IS HIGHLY RECOMMENDED TO ONLY RUN THIS TOOL WITH LOCAL, PRIVATE LLMS !!!
# (Due to handling sensitive financial data and information)
#

from datetime import datetime, timedelta
from typing import List, Dict, Callable, Any, Optional, Awaitable
from pydantic import BaseModel, Field
import requests
import re
import json
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion
from actual import Actual
from actual.queries import get_accounts, get_transactions, get_account, get_categories, get_payees


class Tools:

    class Valves(BaseModel):
        base_url: str = Field(
            default="http://localhost:5006",
            description="Base URL of the Actual Server",
            required=True,
        )
        password: str = Field(
            default="", description="Actual password for authentication", required=True
        )
        encryption_password: str = Field(
            default=None, description="Optional: Password for the file encryption, if set", required=False
        )
        file_budget_name: str = Field(
            default="", description="The exact name of the Budget (or 'file') to query."
        )
        debug: bool = Field(
            default=False, description="Enables verbose debugging in OpenWebUI logs"
        )
        citations: bool = Field(
            default=False,
            description="Enables in-line 'citations', proving response is sourced from real Actual data. Looks messy, but is useful for debugging/differentiating from hallucinations",
        )
        pass

    def __init__(self):
        self.valves = self.Valves()
        self.citation = self.valves.citations
        if self.valves.debug:
            print("actual_api_request: init")
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

        if self.valves.debug:
            print(f"actual_api_request: determining which Actual data to retrieve")
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": "Determining which Actual data to retrieve...",
                    "done": False,
                },
            }
        )

        # Use LLM to decide which API endpoint to call
        tools_metadata = [
            {
                "id": "accounts",
                "description": "Retrieve a list of all account and balance details from Actual.",
            },
            {
                "id": "transactions",
                "description": "Retrieve a list of all financial transaction details from Actual.",
            },
        ]

        system_prompt = (
            """You are an assistant tasked with retrieving financial data for the user through 'Actual', a financial tracking and budgeting app.
            Do not rely on fake financial data in your own knowledge base;
            instead, determine the best tool below that will be used to query for the user's real 'Actual' data pertaining to the user's request."""
            + "\nTools: "
            + str(tools_metadata)
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
                print(f"actual_api_request: error deciding tool: {e}")
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


        if self.valves.debug:
            print(f"actual_api_request: opening Actual session")
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": f"Opening Actual session",
                    "done": False,
                },
            }
        )


        with Actual(
            base_url=self.valves.base_url,
            password=self.valves.password,
            encryption_password=self.valves.encryption_password,
            file=self.valves.file_budget_name
        ) as actual:

            if endpoint == "accounts":
                
                if self.valves.debug:
                    print(f"actual_api_request: fetching Actual account data")
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Fetching Actual account data",
                            "done": False,
                        },
                    }
                )

                try:
                    processed_accounts = []
                    for acc in get_accounts(actual.session):
                        processed_accounts.append({
                            "name": acc.name,
                            "balance": acc.balance
                        })
                        name = acc.name
                        balance = acc.balance
                        # I don't believe Actual supports "closed" accounts, so skipping "closed" check for now
                    if self.valves.debug:
                        print("actual_api_request: Actual account data fetched successfully")
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": f"Actual account data fetched successfully",
                                "done": True,
                            },
                        }
                    )
                    return {
                        "All Actual Accounts": processed_accounts
                    }
                except Exception as e:
                    if self.valves.debug:
                        print(f"actual_api_request: error while fetching Actual accounts: {str(e)}")
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": f"Actual account data fetch failed",
                                "done": True,
                            },
                        }
                    )
                    return f"Error while fetching Actual accounts: {str(e)}"
                
            elif endpoint == "transactions":
                
                if self.valves.debug:
                    print(f"actual_api_request: fetching Actual transaction data")
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Fetching Actual transaction data",
                            "done": False,
                        },
                    }
                )

                try:

                    categories = get_categories(actual.session)
                    category_lookup = {cat.id: cat.name for cat in categories}

                    payees = get_payees(actual.session)
                    payee_lookup = {pay.id: pay.name for pay in payees}

                    processed_transactions = []
                    for tx in get_transactions(actual.session):
                        account_obj = get_account(actual.session, tx.acct)
                        account = account_obj.name if account_obj else "Unknown Account"
                        processed_transactions.append({
                            "date": tx.get_date(),
                            "payee": payee_lookup.get(tx.payee_id, "No Payee"),
                            "amount": tx.get_amount(),
                            "category": category_lookup.get(tx.category_id, "Uncategorized"),
                            "account": account,
                            "notes": tx.notes
                        })
                        
                    if self.valves.debug:
                        print("actual_api_request: Actual transaction data fetched successfully")
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": f"Actual transaction data fetched successfully",
                                "done": True,
                            },
                        }
                    )
                    return {
                        "All Actual Transactions": processed_transactions
                    }
                except Exception as e:
                    if self.valves.debug:
                        print(f"actual_api_request: error while fetching Actual transactions: {str(e)}")
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": f"Actual transaction data fetch failed",
                                "done": True,
                            },
                        }
                    )
                    return f"Error while fetching Actual transactions: {str(e)}"

        if self.valves.debug:
            print(f"actual_api_request: no matching Actual data found")
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": "No matching Actual data found.",
                    "done": True,
                },
            }
        )
        return "I'm not sure which Actual data to retrieve based on your query."
