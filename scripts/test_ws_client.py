"""Interactive WebSocket Client for Testing Real-Time Bidirectional Streaming."""

import asyncio
import json
import websockets


async def test_websocket_stream(uri: str = "ws://localhost:8000/ws/interact"):
    print(f"Connecting to WebSocket: {uri} ...")

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Sending initial conversation payload...\n")

            # 1. Start initial conversation
            start_payload = {
                "action": "start",
                "user_choices": {"device_class": "Class II", "type": "SaMD"},
                "user_input": "What are the cybersecurity guidelines for medical device software?",
                "useDeviceData": False,
            }
            await websocket.send(json.dumps(start_payload))

            thread_id = None
            print("[Streaming Output]:\n" + "-" * 50)

            while True:
                message = await websocket.recv()
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "thread_id":
                    thread_id = data.get("thread_id")
                    print(f"\n[Thread ID]: {thread_id}\n")

                elif msg_type == "token":
                    print(data.get("content", ""), end="", flush=True)

                elif msg_type == "status":
                    print("\n" + "-" * 50)
                    print(f"[Status Update]: Interrupted={data.get('is_interrupted')}, Next={data.get('next_nodes')}")

                    if data.get("is_interrupted"):
                        print("\n[Interrupt Triggered]: Simulating user feedback resume...")
                        await asyncio.sleep(1)
                        resume_payload = {
                            "action": "resume",
                            "thread_id": thread_id,
                            "user_input": "Please provide guidance on FDA postmarket cybersecurity management.",
                        }
                        await websocket.send(json.dumps(resume_payload))
                    else:
                        print("[Execution Complete]. Closing WebSocket.")
                        break

                elif msg_type == "complete":
                    print("\n[Conversation Complete]")
                    break

                elif msg_type == "error":
                    print(f"\n[Error]: {data.get('message')}")
                    break

    except Exception as e:
        print(f"WebSocket Client Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_websocket_stream())
