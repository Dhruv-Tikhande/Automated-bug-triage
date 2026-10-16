import concurrent.futures
import os
import re
import time

import grpc

import triage_pb2
import triage_pb2_grpc


TARGET_ADDR = os.environ.get("TARGET_ADDR", "localhost:60401")
REQUEST_COUNT = int(os.environ.get("REQUEST_COUNT", "18"))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "9"))
RAFT_NODES = {
    "A": os.environ.get("RAFT_A_ADDR", "raft-a:60401"),
    "B": os.environ.get("RAFT_B_ADDR", "raft-b:60402"),
    "C": os.environ.get("RAFT_C_ADDR", "raft-c:60403"),
}


def open_channel(address):
    return grpc.insecure_channel(f"dns:///{address}")


def leader_hint(message):
    match = re.search(r"try=([A-C])", message)
    return match.group(1) if match else None


def run_request(request_id):
    address = TARGET_ADDR
    resource = "draft" if request_id % 2 else "submission"

    for attempt in range(1, 7):
        try:
            with open_channel(address) as channel:
                stub = triage_pb2_grpc.LockServiceStub(channel)
                reply = stub.AcquireLock(
                    triage_pb2.LockRequest(
                        resource_id=resource,
                        holder_id=request_id,
                        timestamp=request_id,
                    ),
                    timeout=3,
                )

                if reply.granted:
                    time.sleep(0.1)
                    stub.ReleaseLock(
                        triage_pb2.LockRequest(
                            resource_id=resource,
                            holder_id=request_id,
                            timestamp=request_id,
                        ),
                        timeout=3,
                    )
                    print(
                        f"[LoadTest] request={request_id} resource={resource} "
                        f"result=success target={address}",
                        flush=True,
                    )
                    return True

                leader = leader_hint(reply.message)
                if leader:
                    address = RAFT_NODES[leader]
                    print(
                        f"[LoadTest] request={request_id} redirected-to-leader={leader}",
                        flush=True,
                    )
                else:
                    time.sleep(0.2)

        except grpc.RpcError as error:
            print(
                f"[LoadTest] request={request_id} attempt={attempt} "
                f"rpc-error={error.code()}",
                flush=True,
            )
            time.sleep(0.2)

    print(f"[LoadTest] request={request_id} result=failed", flush=True)
    return False


def main():
    print(
        f"[LoadTest] starting requests={REQUEST_COUNT} workers={MAX_WORKERS} "
        f"initial-target={TARGET_ADDR}",
        flush=True,
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(run_request, range(1, REQUEST_COUNT + 1)))

    succeeded = sum(results)
    print(
        f"[LoadTest] complete succeeded={succeeded} failed={REQUEST_COUNT - succeeded}",
        flush=True,
    )

    if succeeded != REQUEST_COUNT:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
