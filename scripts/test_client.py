"""Interactive Python Client for Testing SSE Streaming & Interrupt Resumes."""

import json
import requests
import sys


def stream_interaction(
    base_url: str = "http://localhost:8000",
    thread_id: str = None,
    user_input: str = None,
    user_choices: dict = None,
    use_device_data: bool = False,
    device_data: str = "",
):
    url = f"{base_url}/interact"

    payload = {
        "thread_id": thread_id,
        "user_input": user_input,
        "user_choices": user_choices or {},
        "useDeviceData": use_device_data,
        "userProvidedDeiveceData": device_data,
    }

    print(f"\n[Sending Request] -> {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")

    response = requests.post(url, json=payload, stream=True)

    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return None

    received_thread_id = None
    print("[Streaming Response]:\n" + "-" * 50)

    for chunk in response.iter_lines():
        if not chunk:
            continue
        chunk_str = chunk.decode("utf-8")
        if chunk_str.startswith("data:"):
            json_str = chunk_str[len("data:") :].strip()
            if not json_str:
                continue
            try:
                data = json.loads(json_str)
                if "thread_id" in data and not received_thread_id:
                    received_thread_id = data["thread_id"]
                    print(f"\n[Thread ID Assigned]: {received_thread_id}\n")
                if "response" in data:
                    print(data["response"], end="", flush=True)
                if "error" in data:
                    print(f"\n[Error from stream]: {data['error']}")
            except json.JSONDecodeError:
                pass

    print("\n" + "-" * 50 + "\n[Stream Completed]")
    return received_thread_id


if __name__ == "__main__":
    base_url = "http://localhost:8000"

    print("=========================================================")
    print(" 1. Initial Interactive Stream (Start Conversation)")
    print("=========================================================")
    thread_id = stream_interaction(
        base_url=base_url,
        user_choices={"classification": "Tier 2", "pathway": "Baseline Benchmark"},
        user_input="If I have a novel distributed telemetry system, what is the best compliance pathway?",
        use_device_data=True,
        device_data="AI-enabled telemetry engine providing automated log anomaly detection.",
    )

    if thread_id:
        print("\n=========================================================")
        print(" 2. Resume Interrupted Thread with User Feedback")
        print("=========================================================")
        stream_interaction(
            base_url=base_url,
            thread_id=thread_id,
            user_input="We also have clinical validation data comparing against 12-lead standard ECGs.",
        )
