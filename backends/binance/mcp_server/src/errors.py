"""Custom exceptions for the MCP server."""

class MCPError(Exception):
    """Base exception for all MCP-related errors."""
    pass

class BinanceError(MCPError):
    """Base exception for Binance-related errors."""
    pass

class BinanceAPIError(BinanceError):
    """Exception raised when Binance API request fails."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Binance API error {status_code}: {message}")

class ValidationError(MCPError):
    """Exception raised when input validation fails."""
    pass

class ConfigurationError(MCPError):
    """Exception raised when there's a configuration issue."""
    pass

class ServiceError(MCPError):
    """Exception raised when there's a service-level error."""
    pass

class ConnectionError(MCPError):
    """Exception raised when connection fails."""
    pass

# MongoDB specific exceptions
class MongoDBError(MCPError):
    """Base exception for MongoDB-related errors."""
    pass

class MongoConnectionError(MongoDBError):
    """Exception raised when MongoDB connection fails."""
    pass

class MongoQueryError(MongoDBError):
    """Exception raised when MongoDB query fails."""
    pass
