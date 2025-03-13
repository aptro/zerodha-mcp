from typing import Any, Dict, List, Optional, AsyncIterator
import os
import httpx
from contextlib import asynccontextmanager
from dataclasses import dataclass
from threading import Thread
import webbrowser
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from mcp.server.fastmcp import FastMCP, Context
from kiteconnect import KiteConnect
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Constants
KITE_API_KEY = os.getenv("KITE_API_KEY")
KITE_API_SECRET = os.getenv("KITE_API_SECRET")
REDIRECT_URL = "http://127.0.0.1:5000/zerodha/auth/redirect"
TOKEN_STORE_PATH = os.path.join(os.path.dirname(__file__), ".tokens")

# Initialize FastAPI app for handling redirect
app = FastAPI(title="Zerodha Login Handler")

# Global variables for auth flow
_request_token: Optional[str] = None


@dataclass
class ZerodhaContext:
    """Typed context for the Zerodha MCP server"""

    kite: KiteConnect
    api_key: str
    api_secret: str
    app: FastAPI
    server_thread: Optional[Thread] = None


def load_stored_token() -> Optional[str]:
    """Load stored access token if it exists"""
    try:
        if os.path.exists(TOKEN_STORE_PATH):
            with open(TOKEN_STORE_PATH, "r") as f:
                return f.read().strip()
    except Exception:
        return None
    return None


def save_access_token(token: str):
    """Save access token to file"""
    try:
        with open(TOKEN_STORE_PATH, "w") as f:
            f.write(token)
    except Exception as e:
        print(f"Warning: Could not save access token: {e}")


def start_server():
    """Start the FastAPI server"""
    print("Starting FastAPI server on http://127.0.0.1:5000")
    uvicorn.run(app, host="127.0.0.1", port=5000, log_level="error")


@asynccontextmanager
async def zerodha_lifespan(server: FastMCP) -> AsyncIterator[ZerodhaContext]:
    """Manage application lifecycle for Zerodha integration"""
    # Initialize Kite Connect
    print("Initializing Zerodha context...")

    if not KITE_API_KEY or not KITE_API_SECRET:
        raise ValueError(
            "KITE_API_KEY and KITE_API_SECRET must be set in the .env file"
        )

    kite = KiteConnect(api_key=KITE_API_KEY)

    # Try to load existing token
    stored_token = load_stored_token()
    if stored_token:
        try:
            kite.set_access_token(stored_token)
            # Verify token is still valid with a simple API call
            kite.margins()
            print("Successfully restored previous session")
        except Exception:
            print("Stored token is invalid, will wait for new login...")
            if os.path.exists(TOKEN_STORE_PATH):
                os.remove(TOKEN_STORE_PATH)

    # Create context
    ctx = ZerodhaContext(
        kite=kite,
        api_key=KITE_API_KEY,
        api_secret=KITE_API_SECRET,
        app=app,
    )

    try:
        # Setup FastAPI endpoint for auth callback
        @app.get("/zerodha/auth/redirect")
        async def callback(request_token: str = None, status: str = None):
            """Handle the redirect from Zerodha login"""
            global _request_token

            if status != "success":
                print(f"Login failed with status: {status}")
                raise HTTPException(
                    status_code=400, detail=f"Login failed with status: {status}"
                )
            if not request_token:
                print("No request token received")
                raise HTTPException(status_code=400, detail="No request token received")

            try:
                # Generate session
                print("Generating session with request token")
                data = ctx.kite.generate_session(
                    request_token, api_secret=ctx.api_secret
                )
                access_token = data["access_token"]

                # Save and set the access token
                print("Saving and setting access token")
                save_access_token(access_token)
                ctx.kite.set_access_token(access_token)
                _request_token = request_token
                print("Login successful")

                return HTMLResponse(
                    content="""
                    <html>
                        <body style="font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f5f5f5;">
                            <div style="text-align: center; padding: 2rem; background-color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <h1 style="color: #2ecc71;">Login Successful!</h1>
                                <p>You can close this window now.</p>
                            </div>
                        </body>
                    </html>
                    """
                )
            except Exception as e:
                error_msg = f"Failed to generate session: {str(e)}"
                print(error_msg)
                raise HTTPException(status_code=500, detail=error_msg)

        # Yield the context to the tools
        yield ctx
    finally:
        # Cleanup on shutdown
        print("Shutting down Zerodha context...")
        # Additional cleanup could go here if needed


# Initialize FastMCP server with lifespan and dependencies
mcp = FastMCP(
    "zerodha",
    lifespan=zerodha_lifespan,
    dependencies=["kiteconnect", "fastapi", "uvicorn", "python-dotenv", "httpx"],
)


@mcp.tool()
def initiate_login(ctx: Context) -> Dict[str, Any]:
    """
    Start the Zerodha login flow by opening the login URL in a browser
    and starting a local server to handle the redirect
    """
    try:
        # Reset the request token
        global _request_token
        _request_token = None
        print("Initiating Zerodha login flow")

        # Get strongly typed context
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context

        # Start the local server in a separate thread if not already running
        if not zerodha_ctx.server_thread or not zerodha_ctx.server_thread.is_alive():
            server_thread = Thread(target=start_server)
            server_thread.daemon = True
            server_thread.start()
            zerodha_ctx.server_thread = server_thread

        # Get the login URL
        login_url = zerodha_ctx.kite.login_url()
        print(f"Generated login URL: {login_url}")

        # Open the login URL in browser
        webbrowser.open(login_url)
        print("Opened login URL in browser")

        return {
            "message": "Login page opened in browser. Please complete the login process."
        }
    except Exception as e:
        error_msg = f"Error initiating login: {str(e)}"
        print(error_msg)
        return {"error": error_msg}


@mcp.tool()
def get_request_token(ctx: Context) -> Dict[str, Any]:
    """Get the current request token after login redirect"""
    if _request_token:
        return {"request_token": _request_token}
    return {
        "error": "No request token available. Please complete the login process first."
    }


@mcp.tool()
def get_holdings(ctx: Context) -> List[Dict[str, Any]]:
    """Get user's holdings/portfolio"""
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.holdings()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_positions(ctx: Context) -> Dict[str, Any]:
    """Get user's positions"""
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.positions()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_margins(ctx: Context) -> Dict[str, Any]:
    """Get account margins"""
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.margins()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def place_order(
    ctx: Context,
    tradingsymbol: str,
    exchange: str,
    transaction_type: str,
    quantity: int,
    product: str,
    order_type: str,
    price: Optional[float] = None,
    trigger_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Place an order on Zerodha

    Args:
        tradingsymbol: Trading symbol (e.g., 'INFY')
        exchange: Exchange (NSE, BSE, NFO, etc.)
        transaction_type: BUY or SELL
        quantity: Number of shares/units
        product: Product code (CNC, MIS, NRML)
        order_type: Order type (MARKET, LIMIT, SL, SL-M)
        price: Price for LIMIT orders
        trigger_price: Trigger price for SL orders
    """
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.place_order(
            variety="regular",
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            transaction_type=transaction_type,
            quantity=quantity,
            product=product,
            order_type=order_type,
            price=price,
            trigger_price=trigger_price,
        )
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_quote(ctx: Context, symbols: List[str]) -> Dict[str, Any]:
    """
    Get quote for symbols

    Args:
        symbols: List of symbols (e.g., ['NSE:INFY', 'BSE:RELIANCE'])
    """
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.quote(symbols)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_historical_data(
    ctx: Context, instrument_token: int, from_date: str, to_date: str, interval: str
) -> List[Dict[str, Any]]:
    """
    Get historical data for an instrument

    Args:
        instrument_token: Instrument token
        from_date: From date (format: 2024-01-01)
        to_date: To date (format: 2024-03-13)
        interval: Candle interval (minute, day, 3minute, etc.)
    """
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval=interval,
        )
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def check_and_authenticate(ctx: Context) -> Dict[str, Any]:
    """
    Check if Kite is authenticated and initiate authentication if needed.
    Returns the authentication status and any relevant messages.
    """
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context

        # First try to load existing token
        stored_token = load_stored_token()
        if stored_token:
            try:
                zerodha_ctx.kite.set_access_token(stored_token)
                # Verify token is still valid with a simple API call
                zerodha_ctx.kite.margins()
                return {
                    "status": "authenticated",
                    "message": "Already authenticated with valid token",
                }
            except Exception:
                print("Stored token is invalid, will initiate new login...")
                if os.path.exists(TOKEN_STORE_PATH):
                    os.remove(TOKEN_STORE_PATH)

        # If we reach here, we need to authenticate
        # Call the existing initiate_login function
        login_result = initiate_login(ctx)

        if "error" in login_result:
            return {"status": "error", "message": login_result["error"]}

        return {"status": "login_initiated", "message": login_result["message"]}

    except Exception as e:
        error_msg = f"Error checking/initiating authentication: {str(e)}"
        print(error_msg)
        return {"status": "error", "message": error_msg}


# Mutual Fund Tools


@mcp.tool()
def get_mf_orders(ctx: Context) -> List[Dict[str, Any]]:
    """Get all mutual fund orders"""
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.mf_orders()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def place_mf_order(
    ctx: Context,
    tradingsymbol: str,
    transaction_type: str,
    amount: float,
    tag: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Place a mutual fund order

    Args:
        tradingsymbol: Trading symbol (e.g., 'INF090I01239')
        transaction_type: BUY or SELL
        amount: Amount to invest or redeem
        tag: Optional tag for the order
    """
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.place_mf_order(
            tradingsymbol=tradingsymbol,
            transaction_type=transaction_type,
            amount=amount,
            tag=tag,
        )
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def cancel_mf_order(ctx: Context, order_id: str) -> Dict[str, Any]:
    """
    Cancel a mutual fund order

    Args:
        order_id: Order ID to cancel
    """
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.cancel_mf_order(order_id=order_id)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_mf_instruments(ctx: Context) -> List[Dict[str, Any]]:
    """Get all available mutual fund instruments"""
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.mf_instruments()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_mf_holdings(ctx: Context) -> List[Dict[str, Any]]:
    """Get user's mutual fund holdings"""
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.mf_holdings()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_mf_sips(ctx: Context) -> List[Dict[str, Any]]:
    """Get all mutual fund SIPs"""
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.mf_sips()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def place_mf_sip(
    ctx: Context,
    tradingsymbol: str,
    amount: float,
    instalments: int,
    frequency: str,
    initial_amount: Optional[float] = None,
    instalment_day: Optional[int] = None,
    tag: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Place a mutual fund SIP (Systematic Investment Plan)

    Args:
        tradingsymbol: Trading symbol (e.g., 'INF090I01239')
        amount: Amount per instalment
        instalments: Number of instalments (minimum 6)
        frequency: weekly, monthly, or quarterly
        initial_amount: Optional initial amount
        instalment_day: Optional day of month/week for instalment (1-31 for monthly, 1-7 for weekly)
        tag: Optional tag for the SIP
    """
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.place_mf_sip(
            tradingsymbol=tradingsymbol,
            amount=amount,
            instalments=instalments,
            frequency=frequency,
            initial_amount=initial_amount,
            instalment_day=instalment_day,
            tag=tag,
        )
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def modify_mf_sip(
    ctx: Context,
    sip_id: str,
    amount: Optional[float] = None,
    frequency: Optional[str] = None,
    instalments: Optional[int] = None,
    instalment_day: Optional[int] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Modify a mutual fund SIP

    Args:
        sip_id: SIP ID to modify
        amount: New amount per instalment
        frequency: New frequency (weekly, monthly, or quarterly)
        instalments: New number of instalments
        instalment_day: New day of month/week for instalment
        status: SIP status (active or paused)
    """
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.modify_mf_sip(
            sip_id=sip_id,
            amount=amount,
            frequency=frequency,
            instalments=instalments,
            instalment_day=instalment_day,
            status=status,
        )
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def cancel_mf_sip(ctx: Context, sip_id: str) -> Dict[str, Any]:
    """
    Cancel a mutual fund SIP

    Args:
        sip_id: SIP ID to cancel
    """
    try:
        zerodha_ctx: ZerodhaContext = ctx.request_context.lifespan_context
        return zerodha_ctx.kite.cancel_mf_sip(sip_id=sip_id)
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # We don't need the main function anymore since MCP handles the lifecycle
    print("Starting Zerodha MCP server...")
    mcp.run()
