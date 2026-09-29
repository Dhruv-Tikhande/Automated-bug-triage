import sys

import grpc

import triage_pb2
import triage_pb2_grpc


def run(port):
    address = f"localhost:{port}"

    with grpc.insecure_channel(address) as channel:
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
    run(sys.argv[1])