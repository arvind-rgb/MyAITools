#!/usr/bin/env python3.11
"""
Porter.in MCP server — exposes Porter delivery tools to Claude Code.

Run via: python3.11 porter_mcp_server.py
Registered automatically via .mcp.json in the project root.

Tools available to Claude:
  porter_check_session    — check if saved Porter session is valid
  porter_setup_session    — open headed browser for manual OTP login
  porter_get_quote        — get fare estimate between two addresses
  porter_book_delivery    — book a two-wheeler delivery
  porter_track_order      — get live status of an existing order
"""
import asyncio
import sys
import os

# Ensure project root is on path so porter_browser imports correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
from porter_browser import PorterBrowser

mcp = FastMCP("porter-delivery")


@mcp.tool()
async def porter_check_session() -> dict:
    """
    Check whether the saved Porter browser session is still valid.
    Returns {"logged_in": true} if authenticated, {"logged_in": false} if not.
    If not logged in, ask the user to run porter_setup_session.
    """
    async with PorterBrowser() as pb:
        logged_in = await pb.is_logged_in()
    return {"logged_in": logged_in}


@mcp.tool()
async def porter_setup_session() -> dict:
    """
    Open a visible browser window for the user to log in to Porter manually
    (phone number + OTP). The authenticated session is saved to disk.
    This only needs to be run once, or when the session expires (~30 days).
    Returns {"ok": true, "message": "..."} on success.
    """
    async with PorterBrowser(headless=False) as pb:
        return await pb.setup_session_interactive()


@mcp.tool()
async def porter_get_quote(pickup_address: str, drop_address: str) -> dict:
    """
    Get a fare estimate for a Porter two-wheeler delivery.

    Args:
        pickup_address: Full pickup address including area and city (e.g. "HSR Layout Sector 1, Bangalore")
        drop_address:   Full drop/delivery address (e.g. "Koramangala 5th Block, Bangalore")

    Returns estimated_cost as a rupee string (e.g. "₹85") or an error dict.
    """
    async with PorterBrowser() as pb:
        return await pb.get_quote(pickup_address, drop_address)


@mcp.tool()
async def porter_book_delivery(
    pickup_address: str,
    drop_address: str,
    contact_name: str,
    contact_phone: str,
    pickup_time: str = "now",
    notes: str = "",
) -> dict:
    """
    Book a two-wheeler delivery on Porter.

    Args:
        pickup_address: Full pickup address (Google Maps autocomplete will be used)
        drop_address:   Full delivery destination address
        contact_name:   Receiver's full name
        contact_phone:  Receiver's 10-digit mobile number (no country code, e.g. "9876543210")
        pickup_time:    "now" for immediate pickup, or ISO 8601 datetime for scheduled
                        (e.g. "2026-04-22T14:30:00" for today at 2:30 PM)
        notes:          Optional internal notes stored in Bhookle (not sent to Porter)

    Returns porter_order_id, estimated_cost, and booking status.
    Call porter_check_session first if unsure whether session is active.
    """
    async with PorterBrowser() as pb:
        result = await pb.book_delivery(
            pickup=pickup_address,
            drop=drop_address,
            contact_name=contact_name,
            contact_phone=contact_phone,
            pickup_time=pickup_time,
        )
    if result.get("ok"):
        result["notes"] = notes
    return result


@mcp.tool()
async def porter_track_order(porter_order_id: str) -> dict:
    """
    Track the current status and ETA of an existing Porter delivery.

    Args:
        porter_order_id: The order ID returned when the delivery was booked
                         (e.g. "ORD-12345" or whatever Porter shows on the confirmation screen)

    Returns {"status": "...", "eta": "...", "order_id": "..."} or an error dict.
    """
    async with PorterBrowser() as pb:
        return await pb.track_order(porter_order_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
