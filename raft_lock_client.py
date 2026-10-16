import os
import sys

import grpc

import triage_pb2
import triage_pb2_grpc


def run(target):
    address = target if ":" in target else f"localhost:{target}"
    channel_target = f"dns:///{address}" if not address.startswith("localhost:") else address

    with grpc.insecure_channel(channel_target) as channel:
        stub = triage_pb2_grpc.LockServiceStub(channel)

        reply = stub.AcquireLock(
            triage_pb2.LockRequest(
                resource_id="draft",
                holder_id=99,
                timestamp=1,
            ),
            timeout=2,
        )

        print(f"Target: {address}")
        print(f"Granted: {reply.granted}")
        print(f"Message: {reply.message}")

        if reply.granted:
            stub.ReleaseLock(
                triage_pb2.LockRequest(
                    resource_id="draft",
                    holder_id=99,
                    timestamp=1,
                ),
                timeout=2,
            )
            print("Lock released.")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TARGET_ADDR", "localhost:60401"))
