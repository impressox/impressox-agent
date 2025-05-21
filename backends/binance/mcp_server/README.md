# Binance MCP Server

A FastMCP server implementation for Binance market data, social media analysis, and trading insights using Python MCP SDK.

## Features

- Real-time market information for trading pairs
- Market-wide data with top trading pairs by volume
- Trading alpha insights based on volume and price patterns
- Social media monitoring and analytics for Binance accounts
- FastMCP-based architecture with async/await support
- Strong typing with Pydantic models
- Comprehensive test coverage

## Data Sources

1. Binance API:
   - Real-time trading data
   - Market statistics
   - Price and volume information

2. MongoDB:
   - Historical social media data
   - Engagement metrics
   - Twitter posts from official Binance accounts

## Development Setup

1. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings
# Required variables:
# - BINANCE_API_KEY
# - TWITTER_TOKEN
# - MONGO_URL
# - TWITTER_USERS
```

## Running the Server

### Local Development
```bash
# Run directly
./run.sh

# Or using Python module
python -m src.server
```

### Using Docker
```bash
# Build image
docker build -t binance-mcp .

# Run container
docker run -p 5000:5000 \
  --env-file .env \
  binance-mcp
```

### Using Docker Compose
```bash
docker-compose up binance-mcp
```

## Available Tools

1. Get Market Info
```python
# Get specific symbol info
await mcp.use_tool(
    "binance-info", 
    "get_market_info",
    {"symbol": "BTCUSDT"}
)

# Get market-wide data
await mcp.use_tool(
    "binance-info",
    "get_market_info",
    {}
)
```

2. Get Trading Alpha
```python
await mcp.use_tool(
    "binance-info",
    "get_alpha",
    {"timeframe": "24h"}  # Options: "24h", "7d", "30d"
)
```

3. Get Social Media Data
```python
await mcp.use_tool(
    "binance-info",
    "get_binance_social",
    {
        "days_ago": 0,  # 0 = today only, N = look back N days
        "posts_per_user": 10  # Max posts per user (max 10)
    }
)
```

## Testing

The project uses pytest for testing. Tests are organized in the `src/tests` directory.

### Running Tests

```bash
# Install test dependencies and run all tests
./test.sh --install

# Run specific test file
./test.sh src/tests/test_server.py

# Run tests with specific marker
./test.sh -m "integration"

# Run tests with coverage report
./test.sh --cov
```

### Test Categories

- Unit tests: Basic component testing (`-m unit`)
- Integration tests: End-to-end testing (`-m integration`)
- Async tests: Tests for async functionality (`-m asyncio`)
- Slow tests: Long-running tests (`-m slow`)

## Project Structure

```
mcp_server/
├── src/                  # Source code
│   ├── __init__.py
│   ├── server.py        # FastMCP server with tools
│   ├── services/        # Business logic
│   │   ├── binance.py   # Binance API service
│   │   └── mongodb.py   # MongoDB service
│   ├── types.py         # Type definitions
│   ├── errors.py        # Custom exceptions
│   └── tests/           # Test suite
├── Dockerfile           # Docker build
├── docker-compose.yml   # Docker compose config
├── requirements.txt     # Dependencies
├── run.sh              # Server runner
├── test.sh             # Test runner
└── pytest.ini          # Test configuration
```

## Error Handling

The server implements custom error handling:
- BinanceAPIError: Binance API errors
- ConnectionError: Network connection issues
- ServiceError: Internal service errors
- ValidationError: Input validation failures
- MongoDBError: MongoDB-related errors
  - MongoConnectionError: Connection failures
  - MongoQueryError: Query execution failures

## Environmental Variables

Required:
- MONGO_URL: MongoDB connection URL
- TWITTER_USERS: Comma-separated list of Twitter users to monitor 
  (default: binance,BinanceWallet)
- BINANCE_API_KEY: Binance API key
- TWITTER_TOKEN: Twitter API token
- MCP_HOST: Server host (default: 0.0.0.0)
- MCP_PORT: Server port (default: 5000)

Optional:
- LOG_LEVEL: Logging level (default: INFO)
- DEBUG: Enable debug mode (default: false)
- MAX_POSTS_PER_USER: Maximum posts to fetch per user (default: 10)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License
