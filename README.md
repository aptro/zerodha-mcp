# Zerodha MCP Integration
[![smithery badge](https://smithery.ai/badge/@aptro/zerodha-mcp)](https://smithery.ai/server/@aptro/zerodha-mcp)

This project integrates Zerodha's trading platform with Claude AI using the Multi-Cloud Plugin (MCP) framework, allowing you to interact with your Zerodha trading account directly through Claude.

## Setup Instructions

### Installing via Smithery

To install zerodha-mcp for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@aptro/zerodha-mcp):

```bash
npx -y @smithery/cli install @aptro/zerodha-mcp --client claude
```

### 1. Create a Zerodha Developer Account

1. Go to [Kite Connect](https://developers.kite.trade/) and sign up for a developer account
2. Log in to your account at [developers.kite.trade](https://developers.kite.trade/)

### 2. Create a New App

1. Navigate to the "Apps" section in your Kite Developer dashboard
2. Click on "Create a new app"
3. Fill in the required details:
   - App Name: Choose a descriptive name (e.g., "Claude Zerodha Integration")
   - App Category: Select "Personal" or appropriate category
   - Redirect URL: Set to `http://127.0.0.1:5000/zerodha/auth/redirect`
   - Description: Briefly describe your application's purpose
4. Submit the form to create your app

### 3. Get API Credentials

After creating your app, you'll receive:
- API Key (also called Consumer Key)
- API Secret (also called Consumer Secret)

These credentials will be displayed on your app's details page.

### 4. Configure Environment Variables

1. Create a `.env` file in the root directory of this project
2. Add your API credentials to the file:

```
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
```

Replace `your_api_key_here` and `your_api_secret_here` with the actual credentials from step 3.

### 5. Install Dependencies

Make sure you have all required dependencies installed:

```bash
uv pip install kiteconnect fastapi uvicorn python-dotenv httpx
```

### 6. Install MCP config on your Claude desktop app

Install the MCP config on your Claude desktop app:

```bash
mcp install main.py
```

This command registers the Zerodha plugin with Claude, making all trading functionality available to the AI.

## Usage

After setup, you can interact with your Zerodha account via Claude using the following features:

### Authentication

```
Can you please check if I'm logged into my Zerodha account and authenticate if needed?
```

### Stocks and General Trading

- Check account margins: `What are my current margins on Zerodha?`
- View portfolio holdings: `Show me my current holdings on Zerodha`
- Check current positions: `What positions do I currently have open on Zerodha?`
- Get quotes for symbols: `What's the current price of RELIANCE and INFY on NSE?`
- Place an order: `Place a buy order for 10 shares of INFY at market price on NSE`
- Get historical data: `Can you show me the historical price data for SBIN for the last 30 days?`

### Mutual Funds

- View mutual fund holdings: `Show me my mutual fund holdings on Zerodha`
- Get mutual fund orders: `List all my mutual fund orders on Zerodha`
- Place a mutual fund order: `Place a buy order for ₹5000 in the mutual fund with symbol INF090I01239`
- Cancel a mutual fund order: `Cancel my mutual fund order with order ID 123456789`
- View SIP details: `Show all my active SIPs on Zerodha`
- Create a new SIP: `Set up a monthly SIP of ₹2000 for the fund with symbol INF090I01239 for 12 installments`
- Modify an existing SIP: `Change my SIP with ID 987654321 to ₹3000 per month`
- Cancel a SIP: `Cancel my SIP with ID 987654321`
- Browse available mutual funds: `Show me a list of available mutual funds on Zerodha`

## Authentication Flow

The first time you use any Zerodha functionality, Claude will:
1. Start a local server on port 5000
2. Open a browser window for Zerodha login
3. After successful login, store the access token for future sessions

Your session will remain active until the token expires (typically 24 hours). When the token expires, Claude will automatically initiate the login flow again.

## Available MCP Tools

This plugin offers the following MCP tools that Claude can use:

### Authentication
- `check_and_authenticate` - Verifies authentication status and initiates login if needed
- `initiate_login` - Starts the Zerodha login flow
- `get_request_token` - Retrieves the request token after login

### Stock/General Trading
- `get_holdings` - Retrieves portfolio holdings
- `get_positions` - Gets current positions
- `get_margins` - Retrieves account margins
- `place_order` - Places a trading order
- `get_quote` - Gets quotes for specified symbols
- `get_historical_data` - Retrieves historical price data

### Mutual Funds
- `get_mf_orders` - Retrieves mutual fund orders
- `place_mf_order` - Places a mutual fund order
- `cancel_mf_order` - Cancels a mutual fund order
- `get_mf_instruments` - Gets available mutual fund instruments
- `get_mf_holdings` - Retrieves mutual fund holdings
- `get_mf_sips` - Gets active SIPs
- `place_mf_sip` - Creates a new SIP
- `modify_mf_sip` - Modifies an existing SIP
- `cancel_mf_sip` - Cancels a SIP

## Troubleshooting

- If you encounter authentication issues, try removing the `.tokens` file and restart the authentication process
- Make sure your Zerodha credentials in the `.env` file are correct
- Ensure port 5000 is not being used by another application
- For persistent issues, check Zerodha's API status at [status.zerodha.com](https://status.zerodha.com)

## Security Notes

- Your Zerodha API credentials are stored only in your local `.env` file
- Access tokens are stored in the `.tokens` file in the project directory
- No credentials are transmitted to Claude or any third parties
- All authentication happens directly between you and Zerodha's servers
