import sys
import time
import threading
from concurrent import futures

import grpc

import triage_pb2
import triage_pb2_grpc


PEERS = {
    1: "localhost:60051",
    2: "localhost:60052",
    3: "localhost:60053",
}


class Node:
    def __init__(self, node_id: int):
        self.id = node_id
        self.peers = {nid: addr for nid, addr in PEERS.items() if nid != node_id}
        self.clock = 0
        self.state = "RELEASED"
        self.request_time = None
        self.lock = threading.Lock()
        self.deferred = []

    def tick(self) -> int:
        with self.lock:
            self.clock += 1
            return self.clock

    def update(self, received_ts: int) -> int:
        with self.lock:
            self.clock = max(self.clock, received_ts) + 1
            return self.clock

    def serve(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        triage_pb2_grpc.add_MutexServiceServicer_to_server(MutexServicer(self), server)
        server.add_insecure_port(PEERS[self.id])
        server.start()
        print(f"Node-{self.id}: listening on {PEERS[self.id]}")
        return server

    def _call_with_retry(self, peer_id: int, addr: str, my_ts: int, max_wait: int = 30):
        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                with grpc.insecure_channel(addr) as channel:
                    stub = triage_pb2_grpc.MutexServiceStub(channel)
                    return stub.RequestAccess(
                        triage_pb2.AccessRequest(node_id=self.id, timestamp=my_ts)
                    )
            except grpc.RpcError:
                time.sleep(0.5)
        raise RuntimeError(f"Node-{self.id}: could not reach Node-{peer_id} at {addr}")

    def request_cs(self):
        my_ts = self.tick()
        with self.lock:
            self.state = "WANTED"
            self.request_time = my_ts
        print(f"Node-{self.id}: WANTS critical section at ({my_ts}, {self.id})")

        for peer_id, addr in self.peers.items():
            reply = self._call_with_retry(peer_id, addr, my_ts)
            updated_clock = self.update(reply.timestamp)
            print(
                f"Node-{self.id}: GRANTED by Node-{peer_id} "
                f"with reply ({reply.timestamp}, {reply.node_id}); local clock -> {updated_clock}"
            )

        with self.lock:
            self.state = "HELD"
        print(f"Node-{self.id}: ENTERED critical section")
        time.sleep(0.5)
        self.release_cs()

    def release_cs(self):
        with self.lock:
            self.state = "RELEASED"
            self.request_time = None
            to_release, self.deferred = self.deferred, []
        print(f"Node-{self.id}: RELEASED critical section")
        for event in to_release:
            event.set()


class MutexServicer(triage_pb2_grpc.MutexServiceServicer):
    def __init__(self, node: Node):
        self.node = node

    def RequestAccess(self, request, context):
        updated_clock = self.node.update(request.timestamp)

        with self.node.lock:
            defer = (
                self.node.state == "HELD"
                or (
                    self.node.state == "WANTED"
                    and self.node.request_time is not None
                    and (self.node.request_time, self.node.id)
                    < (request.timestamp, request.node_id)
                )
            )

        if defer:
            print(
                f"Node-{self.node.id}: DEFERS Node-{request.node_id} "
                f"for request ({request.timestamp}, {request.node_id}); local clock -> {updated_clock}"
            )
            event = threading.Event()
            with self.node.lock:
                self.node.deferred.append(event)
            event.wait()
        else:
            print(
                f"Node-{self.node.id}: GRANTS Node-{request.node_id} "
                f"for request ({request.timestamp}, {request.node_id}); local clock -> {updated_clock}"
            )

        send_ts = self.node.tick()
        return triage_pb2.AccessReply(node_id=self.node.id, timestamp=send_ts)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python node.py <node_id>")

    node_id = int(sys.argv[1])
    if node_id not in PEERS:
        raise SystemExit(f"node_id must be one of {sorted(PEERS)}")

    node = Node(node_id)
    server = node.serve()
    try:
        time.sleep(6)
        node.request_cs()
        time.sleep(2)
    finally:
        server.stop(0)


if __name__ == "__main__":
    main()
