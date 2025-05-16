import sys

if __name__ == "__main__":
    code = sys.stdin.read()
    try:
        exec_globals = {}
        exec(code, exec_globals)
        print(exec_globals.get("output", ""))
    except Exception as e:
        print(f"Error: {e}")
