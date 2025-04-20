import asyncio

from fastmcp import Client


async def interact_with_server():
    print("--- Creating Client ---")

    # Option 1: Connect to a server run via `python my_server.py` (uses stdio)
    # client = Client("my_server.py")

    # Option 2: Connect to a server run via `fastmcp run ... --transport sse --port 8080`
    client = Client("http://localhost:8080/sse")  # Use the correct URL/port

    try:
        async with client:
            print("--- Client Connected ---")

            constitutions = await client.list_resources()
            print(f"Constitutions: {constitutions}")

            # Read the 'constitution' resource
            config_data = await client.read_resource("constitutions://list")
            print(f"config resource: {config_data}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("--- Client Interaction Finished ---")


if __name__ == "__main__":
    asyncio.run(interact_with_server())
