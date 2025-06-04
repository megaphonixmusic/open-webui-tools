"""
title: Actual API Request
description: Retrieves user's financial information (accounts or transactions) from Actual API to answer personal finance questions
author: megaphonix
author_url: https://github.com/megaphonixmusic
version: 0.3.0
required_open_webui_version: 0.6.5
requirements: actualpy>=0.12.1
"""

# !!! IMPORTANT: IT IS HIGHLY RECOMMENDED TO ONLY RUN THIS TOOL WITH LOCAL, PRIVATE LLMS !!!
# (Due to handling sensitive financial data and information)
#
# v0.3.0 [2025-06-03]
# - Updated system prompt and logic for more efficient data filtering by date(s)
#
# v0.2.0 [2025-05-07]
# - Refactored code
# - Added Valves for 'Currency' (currently unused), 'Context Format', 'Debug'

from datetime import datetime, timedelta, date
from typing import List, Dict, Callable, Any, Optional, Awaitable, Literal
from pydantic import BaseModel, Field
import requests
import re
import json
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion
from actual import Actual
from actual.queries import get_accounts, get_transactions, get_account, get_categories, get_payees

def format_currency(amount: float) -> str:
        if amount < 0:
            return f"-{abs(amount):,.2f}"
        else:
            return f"{amount:,.2f}"

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
        BASE_URL: str = Field(
            default="http://localhost:5006",
            title="Base URL",
            description="Base URL of the Actual Server",
            required=True,
        )
        PASSWORD: str = Field(
            default="",
            description="Actual password for authentication",
            required=True
        )
        ENCRYPTION_PASSWORD: str = Field(
            default="",
            description="Optional: Password for the file encryption, if set",
            required=False
        )
        FILE_BUDGET_NAME: str = Field(
            default="",
            title="File (Budget) Name",
            description="The exact name of the Budget (or 'file') to query.",
            required=True
        )
        CURRENCY: str = Field(
            default="USD",
            description="Currency format. Actual is currency agnostic, so this is purely for the LLM's awareness.",
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
            description="Enables in-line 'citations', proving response is sourced from real Actual data. Looks messy, but is useful for debugging/differentiating from hallucinations",
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
            description="Determining which Actual data to retrieve...",
            debug=debugState
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

        system_prompt = f"""
            You are an assistant retrieving Actual Budget financial data based on a user's query.

            Choose one of the tools below:
            {tools_metadata}

            Return a list:
            - [] if no tool applies
            - ['accounts'] for account/balance-related queries
            - ['transactions'] for transaction queries with no clear date range
            - ['transactions', startDate, endDate] for transaction queries with a clear date range

            
            For 'transactions':
            - If the query uses **explicit calendar language** (e.g. "2nd week of May", "March 2024", "May 5–9"), interpret it literally and return accurate ISO 8601 start and end dates.
            - If the query uses **relative time** (e.g. "last week", "past 3 days", "this month"), compute dates relative to today ({str(date.today())}).
            - If no date is mentioned, return ['transactions'] without dates.

            Examples:
            - "What's in my checking account?" → ['accounts']
            - "How much did I spend last week?" → ['transactions', '2025-05-27', '2025-06-02']
            - "How much did I spend on groceries?" → ['transactions']
            - "How much did I spend in the 2nd week of May?" → ['transactions', '2025-05-05', '2025-05-11']

            Only return the list. No explanations.
            """

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
            startDate = None
            endDate = None
            if match:
                try:
                    params = json.loads(match.group(0))
                    if debugState == "Full":
                        print(f'LLM Response: {params}')
                    if isinstance(params, list) and params:
                        dataType = params[0]
                        if len(params) == 2:
                            startDate = params[1]
                            endDate = str(date.today())
                        elif len(params) == 3:
                            startDate = params[1]
                            endDate = params[2]
                        if debugState == "Full":
                            print(f"Parsed dataType: {dataType}")
                            print(f"Parsed startDate: {startDate}")
                            print(f"Parsed endDate: {endDate}")
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            determinationError = "Error occurred while determining what Actual data to retrieve."
            await emitter.emit(
                status="error",
                description=f"{determinationError} {e}",
                done=True,
                err=e,
                debug=debugState
            )
            return determinationError

        await emitter.emit(
            description="Opening Actual session...",
            debug=debugState
        )

        with Actual(
            base_url=self.valves.BASE_URL,
            password=self.valves.PASSWORD,
            encryption_password=self.valves.ENCRYPTION_PASSWORD,
            file=self.valves.FILE_BUDGET_NAME
        ) as actual:

            if dataType == "accounts":
                
                await emitter.emit(
                    description="Fetching Actual account data...",
                    debug=debugState
                )

                try:
                    processed_accounts_json = {"All Actual Accounts": []}
                    processed_accounts_markdown = """
                        | Account Name | Balance |\n
                        | --- | ---: |\n
                        """
                    processed_accounts_plaintext = "All Actual Accounts:\n"
                    for acc in get_accounts(actual.session):
                        balance = round(float(acc.balance), 2)
                        processed_accounts_json["All Actual Accounts"].append({
                            "name": acc.name,
                            "balance": balance
                        })
                        processed_accounts_markdown += f"| {acc.name} | {balance} |\n"
                        processed_accounts_plaintext += f"- {acc.name}: {balance}\n"
                    await emitter.emit(
                        status="complete",
                        description="Actual account data fetched successfully",
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
                    acctFail = "Actual account data fetch failed."
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
                    description="Fetching Actual transaction data",
                    debug=debugState
                )

                try:
                    categories = get_categories(actual.session)
                    category_lookup = {cat.id: cat.name for cat in categories}

                    payees = get_payees(actual.session)
                    payee_lookup = {pay.id: pay.name for pay in payees}

                    transactions = get_transactions(actual.session, startDate, endDate)

                    processed_transactions_json = {"All Actual Transactions": []}
                    processed_transactions_markdown = """
                        | Transaction Date | Payee | Amount | Category | Account | Notes |\n
                        | --- | --- | ---: | --- | --- | --- |\n
                        """
                    processed_transactions_plaintext = "All Actual Transactions:\n"
                    for tx in get_transactions(actual.session):
                        account_obj = get_account(actual.session, tx.acct)
                        account = account_obj.name if account_obj else "Unknown Account"
                        category = category_lookup.get(tx.category_id, "Uncategorized")
                        payee = payee_lookup.get(tx.payee_id, "No Payee")
                        
                        # Filter out Starting Balances (these aren't "transactions")
                        isStartingBalance = (category in {"Starting Balances", "Starting Balance"}) or (payee in {"Starting Balances", "Starting Balance"})
                        if not isStartingBalance:
                            transactionDate = tx.get_date().isoformat()
                            amount = format_currency(float(tx.amount/100))
                            processed_transactions_json["All Actual Transactions"].append({
                                "date": transactionDate,
                                "payee": payee,
                                "amount": amount,
                                "category": category,
                                "account": account,
                                "notes": tx.notes
                            })
                            processed_transactions_markdown += f"| {transactionDate} | {payee} | {amount} | {category} | {account} | {tx.notes} |\n"
                            processed_transactions_plaintext += f"- Date: {transactionDate}, Payee: {payee}, Amount: {amount}, Category: {category}, Account: {account}, Notes: {tx.notes}\n"
                    await emitter.emit(
                        status="complete",
                        description="Actual transaction data fetched successfully",
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
                    transactionFail = "Actual transaction data fetch failed."
                    await emitter.emit(
                        status="error",
                        description=transactionFail,
                        done=True,
                        err=e,
                        debug=debugState
                    )
                    return f"{transactionFail} Error: {str(e)}"

        # If all else fails...
        
        finalError = "No matching Actual data found."
        await emitter.emit(
                status="error",
                description=f"{finalError}",
                done=True,
                debug=debugState
            )
        return finalError