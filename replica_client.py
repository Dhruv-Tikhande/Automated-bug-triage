import threading
import time

import grpc

import replica_pb2
import replica_pb2_grpc


REPLICAS = {
    "A": "localhost:60301",
    "B": "localhost:60302",
    "C": "localhost:60303",
}


def save(replica_name, key, content):
    with grpc.insecure_channel(REPLICAS[replica_name]) as channel:
        stub = replica_pb2_grpc.ReplicaServiceStub(channel)

        acknowledgement = stub.SaveValue(
            replica_pb2.ValueUpdate(
                key=key,
                content=content,
                lamport_timestamp=0,
                origin_replica="",
            )
        )

        print(
            f"[Client] Saved on Replica-{replica_name}: \"{content}\" "
            f"-> accepted={acknowledgement.accepted}, "
            f"replica_ts={acknowledgement.lamport_timestamp}"
        )


def read(replica_name, key):
    with grpc.insecure_channel(REPLICAS[replica_name]) as channel:
        stub = replica_pb2_grpc.ReplicaServiceStub(channel)

        state = stub.GetValue(
            replica_pb2.ValueQuery(key=key)
        )

        return (
            state.content,
            state.lamport_timestamp,
            state.origin_replica,
        )


def main():
    key = "shared-key-1"

    print("=== Simulating two concurrent writers hitting DIFFERENT replicas ===\n")

    writer_one = threading.Thread(
        target=save,
        args=("A", key, "value-from-writer-1"),
    )

    writer_two = threading.Thread(
        target=save,
        args=("C", key, "value-from-writer-2"),
    )

    writer_one.start()
    time.sleep(0.05)
    writer_two.start()

    writer_one.join()
    writer_two.join()

    print("\n=== Immediately after writes (replicas may still be mid-gossip) ===")

    for replica_name in REPLICAS:
        content, timestamp, origin = read(replica_name, key)
        print(
            f"Replica-{replica_name}: \"{content}\" "
            f"(ts={timestamp}, origin={origin})"
        )

    print("\nWaiting 2 seconds for gossip to finish propagating...\n")
    time.sleep(2)

    print("=== After convergence window ===")

    results = {}

    for replica_name in REPLICAS:
        content, timestamp, origin = read(replica_name, key)
        results[replica_name] = content
        print(f"Replica-{replica_name}: \"{content}\"")

    if len(set(results.values())) == 1:
        print(
            f"\n*** CONVERGED: all replicas agree on: "
            f"\"{list(results.values())[0]}\" ***"
        )
    else:
        print(f"\n*** NOT YET CONVERGED: {set(results.values())} ***")


if __name__ == "__main__":
    main()