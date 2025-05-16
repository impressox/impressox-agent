import subprocess
from langchain_core.tools import tool
from app.core.tool_registry import register_tool
from app.constants import NodeName

def execute_python_in_docker(code: str, timeout: int = 5):
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",  # Không cho truy cập mạng
        "--cpus", "0.5",
        "--memory", "128m",
        "-i", "hiepht/cpx:python-sandbox-img"
    ]
    try:
        result = subprocess.run(
            cmd, input=code.encode(),
            capture_output=True, timeout=timeout
        )
        return result.stdout.decode() or result.stderr.decode()
    except subprocess.TimeoutExpired:
        return "Timeout"


@register_tool(NodeName.GENERAL_NODE, "safe_python_tool")
@tool
def safe_python_tool(code: str) -> str:
    """
    Execute Python code in a safe environment
    
    Args:
        code (str): The Python code to execute
        
    Returns:
        str: The output of the Python code
    """
    return execute_python_in_docker(code)