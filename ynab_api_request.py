"""
title: YNAB API Request
description: Retrieves user's financial information (accounts or transactions) from YNAB API to answer personal finance questions
author: megaphonix
author_url: https://github.com/megaphonixmusic
version: 0.2.0
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
#
# v0.2.0 [2025-05-07] 
# - Refactored code (now matches Actual API Request more closely)
# - Added Valves for 'Context Format', 'Debug'

from datetime import datetime, timedelta, date
from typing import List, Dict, Callable, Any, Optional, Awaitable, Literal
from pydantic import BaseModel, Field
import requests
import re
import json
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion

def format_currency(amount: float) -> str:
            if amount < 0:
                return f"-${abs(amount):,.2f}"
            else:
                return f"${amount:,.2f}"

class EventEmitter:

    def __init__(self, event_emitter: Callable[[dict], Any] = None):
        self.event_emitter = event_emitter

    async def emit(
        self,
        description="Unknown State",
        status="in_progress",
        done=False,
        err=None,
        debug="Off"
    ):
        if debug in {"Basic", "Full"}:
            debugMsg = f"[actual_api_request] {status}: {description}"
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
        YNAB_BUDGET_ID: str = Field(
            default="",
            title="YNAB Budget ID",
            description="Budget ID to query. Can be obtained with YNAB API (see README)",
            required=True,
        )
        YNAB_ACCESS_TOKEN: str = Field(
            default="",
            title="YNAB Access Token",
            description="YNAB API authorization token",
            required=True
        )
        CONTEXT_FORMAT: Literal["JSON", "Markdown", "Plaintext"] = Field(
            default="JSON",
            description="How to format data passed to LLM for context: JSON, Markdown, Plaintext",
            required=True
        )
        DEBUG: Literal["Off", "Basic", "Full"] = Field(
            default="Off",
            description="Toggle verbose debugging in OpenWebUI logs. Off = none, Basic = status messages, Full = includes raw data",
            required=False
        )
        CITATIONS: bool = Field(
            default=False,
            description="Enables in-line 'citations', proving response is sourced from actual YNAB data. Looks messy, but is useful for debugging/differentiating from hallucinations",
            required=False
        )
        pass

    def __init__(self):
        self.valves = self.Valves()
        self.citation = self.valves.CITATIONS
        pass

    async def _run(
        self,
        query: str,
        __event_emitter__: Callable[[Any], Awaitable[None]],
        __request__: Any,
        __user__: Optional[dict] = None,
        __model__: Optional[dict] = None,
    ) -> str:

        emitter = EventEmitter(__event_emitter__)
        contextFormat = self.valves.CONTEXT_FORMAT
        debugState = self.valves.DEBUG

        await emitter.emit(
            description="Determining which YNAB data to retrieve...",
            debug=debugState
        )

        budget_id = self.valves.YNAB_BUDGET_ID
        access_token = self.valves.YNAB_ACCESS_TOKEN
        headers = {"Authorization": f"Bearer {access_token}"}

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
            f"""You are an assistant tasked with retrieving financial data for the user through 'YNAB' (aka You Need A Budget), a financial tracking and budgeting app.\n
            Determine the best tool below to check for the user's data pertaining to the user's query.\n
            Tools:\n
            {str(tools_metadata)}
            \nIf a tool doesn't match the query, return an empty list []. Otherwise, return a list of matching tool IDs in the format ['tool_id']. Only return the list. Do not return any other text.\n
            Examples of ['accounts'] queries include 'What is my net worth?', 'How much is in my checking account?', 'How much do I owe on my student loans?', 'How much debt do I have?'\n
            Examples of ['transactions'] queries include 'How much total did I spend last week?', 'How many times did I get Starbucks last month?', 'What is my largest purchase year-to-date?'
            """
        )

        prompt = f"Query: {query}"

        payload = {
            "model": __model__.get("id") if isinstance(__model__, dict) else __model__,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
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
            dataType = None
            if match:
                try:
                    tools = json.loads(match.group(0))
                    if isinstance(tools, list) and tools:
                        dataType = tools[0]
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            determinationError = "Error occurred while determining what YNAB data to retrieve."
            await emitter.emit(
                status="error",
                description=f"{determinationError} {e}",
                done=True,
                err=e,
                debug=debugState
            )
            return determinationError

        await emitter.emit(
            description="Opening YNAB session...",
            debug=debugState
        )

        if dataType == "accounts":

            await emitter.emit(
                    description="Fetching YNAB account data...",
                    debug=debugState
                )

            url = f"https://api.ynab.com/v1/budgets/{budget_id}/accounts"
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                apiErr = f"YNAB API error: {response.status_code} {response.text}"
                await emitter.emit(
                    status="error",
                    description=apiErr,
                    done=True,
                    debug=debugState
                )
                return apiErr

            try:
                accounts = response.json().get("data", {}).get("accounts", [])
                if not accounts:
                    noAcctErr = f"No accounts found."
                    await emitter.emit(
                        status="error",
                        description=noAcctErr,
                        done=True,
                        debug=debugState
                    )
                    return noAcctErr

                processed_accounts_json = {"All YNAB Accounts": []}
                processed_accounts_markdown = """
                    | Account Name | Type | Balance |\n
                    | --- | --- | ---: |\n
                    """
                processed_accounts_plaintext = "All YNAB Accounts:\n"
                for acc in accounts:
                    if not acc.get("closed", False):
                        acctName = acc.get("name")
                        acctBalance = acc.get("balance", 0) / 1000.0
                        acctType = acc.get("type")
                        processed_accounts_json["All YNAB Accounts"].append({
                            "name": acctName,
                            "balance": acctBalance,
                            "type": acctType,
                            # Not necessary yet:
                            # "included_in_budget": acc.get("on_budget", False)
                        })
                    processed_accounts_markdown += f"| {acctName} | {acctType} | {acctBalance} |\n"
                    processed_accounts_plaintext += f"- {acctName} ({acctType}): {acctBalance}\n"
                await emitter.emit(
                    status="complete",
                    description="YNAB account data fetched successfully",
                    done=True,
                    debug=debugState
                )
                if contextFormat == "JSON":
                    if debugState == "Full":
                        print(processed_accounts_json)
                    return processed_accounts_json
                elif contextFormat == "Markdown":
                    if debugState == "Full":
                        print(processed_accounts_markdown)
                    return processed_accounts_markdown
                elif contextFormat == "Plaintext":
                    if debugState == "Full":
                        print(processed_accounts_plaintext)
                    return processed_accounts_plaintext
            except Exception as e:
                acctFail = "YNAB account data fetch failed."
                await emitter.emit(
                    status="error",
                    description=acctFail,
                    done=True,
                    err=e,
                    debug=debugState
                )
                return f"{acctFail} Error: {str(e)}"

        elif dataType == "transactions":

            await emitter.emit(
                description="Fetching YNAB transaction data",
                debug=debugState
            )

            url = f"https://api.ynab.com/v1/budgets/{budget_id}/transactions"
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                apiErr = f"YNAB API error: {response.status_code} {response.text}"
                await emitter.emit(
                    status="error",
                    description=apiErr,
                    done=True,
                    debug=debugState
                )
                return apiErr

            try:

                transactions = response.json().get("data", {}).get("transactions", [])
                if not transactions:
                    noTxError = f"No transactions found."
                    await emitter.emit(
                        status="error",
                        description=noTxError,
                        done=True,
                        debug=debugState
                    )
                    return noTxError
                processed_transactions_json = {"All YNAB Transactions": []}
                processed_transactions_markdown = """
                    | Transaction Date | Payee | Amount | Category | Account | Notes |\n
                    | --- | --- | ---: | --- | --- | --- |\n
                    """
                processed_transactions_plaintext = "All YNAB Transactions:\n"
                for tx in transactions:
                    txDate = tx.get("date", "")
                    payee = tx.get("payee_name", "Unknown"),
                    amount = tx.get("amount", 0) / 1000.0
                    category = tx.get("category_name", "Uncategorized")
                    account = tx.get("account_name", "Unknown Account")
                    memo = tx.get("memo", "")
                    processed_transactions_json["All YNAB Transactions"].append({
                        "date": txDate,
                        "payee": payee,
                        "amount": amount,
                        "category": category,
                        "account": account,
                        "memo": memo,
                    })
                    processed_transactions_markdown += f"| {txDate} | {payee} | {amount} | {category} | {account} | {memo} |\n"
                    processed_transactions_plaintext += f"- Date: {txDate}, Payee: {payee}, Amount: {amount}, Category: {category}, Account: {account}, Memo: {memo}\n"
                await emitter.emit(
                    status="complete",
                    description="YNAB transaction data fetched successfully",
                    done=True,
                    debug=debugState
                )
                if contextFormat == "JSON":
                    if debugState == "Full":
                        print(processed_transactions_json)
                    return processed_transactions_json
                elif contextFormat == "Markdown":
                    if debugState == "Full":
                        print(processed_transactions_markdown)
                    return processed_transactions_markdown
                elif contextFormat == "Plaintext":
                    if debugState == "Full":
                        print(processed_transactions_plaintext)
                    return processed_transactions_plaintext
            except Exception as e:
                transactionFail = "YNAB transaction data fetch failed."
                await emitter.emit(
                    status="error",
                    description=transactionFail,
                    done=True,
                    err=e,
                    debug=debugState
                )
                return f"{transactionFail} Error: {str(e)}"

        # If all else fails...
        
        finalError = "No matching YNAB data found."
        await emitter.emit(
                status="error",
                description=f"{finalError}",
                done=True,
                debug=debugState
            )
        return finalError