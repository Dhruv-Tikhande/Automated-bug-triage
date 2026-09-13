import threading
import time

import grpc

import triage_pb2
import triage_pb2_grpc


BACKENDS = [
    "localhost:60201",
    "localhost:60202",
    "localhost:60203",
]

NUM_REQUESTS = 9

# active[i] stores the current in-flight requests for BACKENDS[i].
active = [0] * len(BACKENDS)
lock = threading.Lock()


def pick_least_connections():
    """Choose the least busy backend and reserve its connection slot."""
    with lock:
        index = active.index(min(active))
        active[index] += 1

        print(
            f"[LB] Routing -> {BACKENDS[index]} "
            f"(active connections now: {active})"
        )
        return index


def release(index):
    """Release the backend slot after the RPC finishes or fails."""
    with lock:
        active[index] -= 1
        print(
            f"[LB] Released {BACKENDS[index]} "
            f"(active connections now: {active})"
        )


def handle_request(request_id):
    index = pick_least_connections()
    address = BACKENDS[index]

    try:
        with grpc.insecure_channel(address) as channel:
            stub = triage_pb2_grpc.WorkerServiceStub(channel)

            reply = stub.HandleRequest(
                triage_pb2.WorkRequest(request_id=request_id)
            )

            print(
                f"[LB] Request {request_id} -> "
                f"handled by {reply.handled_by}"
            )
    finally:
        # This must always run so the count does not leak upward.
        release(index)


def main():
    print(f"[LB] Load Balancer starting. Backends: {BACKENDS}")

    threads = []

    for request_id in range(1, NUM_REQUESTS + 1):
        thread = threading.Thread(
            target=handle_request,
            args=(request_id,),
        )
        threads.append(thread)
        thread.start()

        # Simulates requests arriving over time.
        time.sleep(0.15)

    for thread in threads:
        thread.join()

    print("\n[LB] All requests processed.")
    print(f"[LB] Final active connection counts: {active}")


if __name__ == "__main__":
    main()