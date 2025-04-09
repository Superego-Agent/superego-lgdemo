import httpx
import json
import asyncio

# Configuration
API_BASE_URL = "http://localhost:8000/api"
STREAM_ENDPOINT = f"{API_BASE_URL}/runs/stream"

# Example request body - adjust if needed based on configured tools/agents
# This assumes a simple input and minimal config.
# We need at least one configured module for the backend logic.
request_body = {
    "input": {"type": "human", "content": "What is 2 + 2?"}, # Example input, might need adjustment
    "configurable": {
        "thread_id": None, # Start a new thread
        "runConfig": {
            # Provide a minimal valid RunConfig. Assuming 'ConfiguredConstitutionModule'
            # is the expected type based on refactor_plan.md.
            # If no constitutions are needed/available, this might need adjustment.
            "configuredModules": [
                # {
                #     "id": "some-default-id", # Placeholder ID
                #     "title": "Default Minimal Constitution",
                #     "adherence_level": 1
                # }
            ]
        }
    }
}

async def main():
    print(f"Connecting to SSE stream at: {STREAM_ENDPOINT}")
    print(f"Sending request body:\n{json.dumps(request_body, indent=2)}")
    print("-" * 30)
    print("Listening for SSE events...")
    print("-" * 30)

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", STREAM_ENDPOINT, json=request_body) as response:
                if response.status_code != 200:
                    print(f"Error connecting: Status {response.status_code}")
                    error_text = await response.aread()
                    print(f"Response: {error_text.decode()}")
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        event_data = line[len("data:"):].strip()
                        print(f"RAW EVENT DATA: {event_data}")
                        # Optional: Try parsing to see structure during logging
                        # try:
                        #     parsed = json.loads(event_data)
                        #     print(f"PARSED EVENT: {parsed}")
                        # except json.JSONDecodeError:
                        #     print("(Event data is not valid JSON)")
                        # print("-" * 10) # Separator between events

    except httpx.RequestError as exc:
        print(f"An error occurred while requesting {exc.request.url!r}: {exc}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())