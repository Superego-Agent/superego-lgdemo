import functools
import sys
import traceback
from typing import Callable, Any

try:
    from rich.console import Console
    error_console = Console(stderr=True, style="bold red")
    def _print_error(func_name: str, e: Exception):
        error_console.print(f"\n>>> FAILED AT: {func_name} <<<")
        error_console.print(f"    Error: {e.__class__.__name__}: {e}")
        # traceback.print_exc()
except ImportError:
    def _print_error(func_name: str, e: Exception):
        print(f"\n>>> FAILED AT: {func_name} <<<", file=sys.stderr)
        print(f"    Error: {e.__class__.__name__}: {e}", file=sys.stderr)
        # traceback.print_exc()

def shout_if_fails(func: Callable) -> Callable:
    """
    Decorator: Executes function, prints clean error & re-raises on exception.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            _print_error(func.__name__, e)
            raise 
    return wrapper