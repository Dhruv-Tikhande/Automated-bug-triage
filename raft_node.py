import random
import sys
import threading
import time
from concurrent import futures

import grpc

import raft_pb2
import raft_pb2_grpc
import triage_pb2
import triage_pb2_grpc


ALL_NODES = {
    "A": "localhost:60401",
    "B": "localhost:60402",
    "C": "localhost:60403",
}

HEARTBEAT_INTERVAL = 0.5
ELECTION_TIMEOUT_RANGE = (1.5, 3.0)


class RaftNode(
    raft_pb2_grpc.RaftServiceServicer,
    triage_pb2_grpc.LockServiceServicer,
):
    def __init__(self, node_id):
        self.id = node_id
        self.peers = {
            peer_id: address
            for peer_id, address in ALL_NODES.items()
            if peer_id != node_id
        }

        self.lock = threading.Lock()
        self.state = "FOLLOWER"
        self.current_term = 0
        self.voted_for = None
        self.leader_id = None
        self.last_heartbeat = time.time()

        # Experiment 5 coordination state, now controlled by the leader.
        self.coordination_lock = threading.Lock()
        self.locks = {"draft": None, "submission": None}
        self.conditions = {
            "draft": threading.Condition(self.coordination_lock),
            "submission": threading.Condition(self.coordination_lock),
        }

    def log(self, message):
        print(
            f"[{self.id} term={self.current_term} {self.state}] {message}",
            flush=True,
        )

    def _reset_election_timer(self):
        self.last_heartbeat = time.time()

    def _random_timeout(self):
        return random.uniform(*ELECTION_TIMEOUT_RANGE)

    def RequestVote(self, request, context):
        with self.lock:
            if request.term > self.current_term:
                self.current_term = request.term
                self.voted_for = None
                self.state = "FOLLOWER"

            grant = (
                request.term >= self.current_term
                and self.voted_for in (None, request.candidate_id)
            )

            if grant:
                self.voted_for = request.candidate_id
                self._reset_election_timer()
                self.log(
                    f"Voted for {request.candidate_id} "
                    f"(term {request.term})"
                )

            return raft_pb2.VoteReply(
                term=self.current_term,
                vote_granted=grant,
            )

    def AppendEntries(self, request, context):
        with self.lock:
            if request.term >= self.current_term:
                self.current_term = request.term
                self.state = "FOLLOWER"
                self.leader_id = request.leader_id
                self._reset_election_timer()

                return raft_pb2.HeartbeatReply(
                    term=self.current_term,
                    success=True,
                )

            return raft_pb2.HeartbeatReply(
                term=self.current_term,
                success=False,
            )

    def _election_watchdog(self):
        while True:
            timeout = self._random_timeout()

            while True:
                time.sleep(0.1)

                with self.lock:
                    state = self.state
                    elapsed = time.time() - self.last_heartbeat

                if state == "LEADER":
                    break

                if elapsed >= timeout:
                    self._start_election()
                    break

    def _start_election(self):
        with self.lock:
            self.state = "CANDIDATE"
            self.current_term += 1
            self.voted_for = self.id
            term = self.current_term
            self._reset_election_timer()

        self.log("Starting election")
        votes = 1

        for peer_id, address in self.peers.items():
            try:
                with grpc.insecure_channel(address) as channel:
                    stub = raft_pb2_grpc.RaftServiceStub(channel)

                    reply = stub.RequestVote(
                        raft_pb2.VoteRequest(
                            term=term,
                            candidate_id=self.id,
                        ),
                        timeout=1,
                    )

                    if reply.vote_granted:
                        votes += 1

                    elif reply.term > term:
                        with self.lock:
                            self.current_term = reply.term
                            self.state = "FOLLOWER"
                            self.voted_for = None
                        return

            except grpc.RpcError:
                self.log(f"No response from {peer_id} (may be down)")

        with self.lock:
            if (
                self.state == "CANDIDATE"
                and votes > len(ALL_NODES) // 2
            ):
                self.state = "LEADER"
                self.leader_id = self.id
                self.log(
                    f"*** ELECTED LEADER *** "
                    f"({votes}/{len(ALL_NODES)} votes)"
                )
            else:
                self.state = "FOLLOWER"
                self.log(
                    f"Election failed ({votes}/{len(ALL_NODES)} votes) "
                    "- reverting to follower"
                )

    def _heartbeat_loop(self):
        while True:
            time.sleep(HEARTBEAT_INTERVAL)

            with self.lock:
                if self.state != "LEADER":
                    continue

                term = self.current_term

            for peer_id, address in self.peers.items():
                try:
                    with grpc.insecure_channel(address) as channel:
                        stub = raft_pb2_grpc.RaftServiceStub(channel)

                        stub.AppendEntries(
                            raft_pb2.HeartbeatRequest(
                                term=term,
                                leader_id=self.id,
                            ),
                            timeout=1,
                        )

                except grpc.RpcError:
                    pass

    def _is_leader(self):
        with self.lock:
            return self.state == "LEADER", self.leader_id

    def AcquireLock(self, request, context):
        is_leader, leader_id = self._is_leader()

        if not is_leader:
            hint = leader_id or "unknown"
            return triage_pb2.LockReply(
                granted=False,
                message=f"not-leader, try={hint}",
            )

        resource = request.resource_id
        holder = request.holder_id

        if resource not in self.locks:
            return triage_pb2.LockReply(
                granted=False,
                message=f"unknown resource: {resource}",
            )

        condition = self.conditions[resource]

        with condition:
            while self.locks[resource] is not None:
                is_leader, leader_id = self._is_leader()

                if not is_leader:
                    return triage_pb2.LockReply(
                        granted=False,
                        message=f"not-leader, try={leader_id or 'unknown'}",
                    )

                condition.wait(timeout=0.5)

            self.locks[resource] = holder

        self.log(f"Granted '{resource}' to Node-{holder}")

        return triage_pb2.LockReply(
            granted=True,
            message=f"granted by leader {self.id}",
        )

    def ReleaseLock(self, request, context):
        resource = request.resource_id
        holder = request.holder_id

        if resource not in self.locks:
            return triage_pb2.LockReply(
                granted=False,
                message=f"unknown resource: {resource}",
            )

        condition = self.conditions[resource]

        with condition:
            if self.locks[resource] == holder:
                self.locks[resource] = None
                condition.notify_all()

        self.log(f"Released '{resource}' from Node-{holder}")

        return triage_pb2.LockReply(
            granted=True,
            message="released",
        )


def serve(node_id):
    node = RaftNode(node_id)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))

    raft_pb2_grpc.add_RaftServiceServicer_to_server(
        node,
        server,
    )

    triage_pb2_grpc.add_LockServiceServicer_to_server(
        node,
        server,
    )

    port = ALL_NODES[node_id].split(":")[1]

    server.add_insecure_port(f"localhost:{port}")
    server.start()

    print(f"RaftNode-{node_id} listening on {ALL_NODES[node_id]}")

    threading.Thread(
        target=node._election_watchdog,
        daemon=True,
    ).start()

    threading.Thread(
        target=node._heartbeat_loop,
        daemon=True,
    ).start()

    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve(sys.argv[1])