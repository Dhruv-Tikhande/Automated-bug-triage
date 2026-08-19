import sys
import threading
import time
from concurrent import futures

import grpc

import triage_pb2
import triage_pb2_grpc


DETECT = len(sys.argv) > 1 and sys.argv[1] == "detect"


class LockManager(triage_pb2_grpc.LockServiceServicer):
    def __init__(self):
        self.mutex = threading.Lock()
        self.locks = {"draft": None, "submission": None}
        self.wait_for = {}  # holder_id -> resource_id
        self.conditions = {
            "draft": threading.Condition(),
            "submission": threading.Condition(),
        }

    def _would_cycle(self, holder, resource):
        visited = set()
        current_resource = resource

        while True:
            owner = self.locks.get(current_resource)

            if owner is None or owner == holder:
                return owner == holder

            if owner in visited:
                return False

            visited.add(owner)
            current_resource = self.wait_for.get(owner)

            if current_resource is None:
                return False

    def AcquireLock(self, request, context):
        resource = request.resource_id
        holder = request.holder_id
        cond = self.conditions[resource]

        with cond:
            with self.mutex:
                owner = self.locks.get(resource)

                if owner is None:
                    self.locks[resource] = holder
                    self.wait_for.pop(holder, None)
                    return triage_pb2.LockReply(granted=True, message="granted")

                if DETECT and self._would_cycle(holder, resource):
                    print(
                        f"[LockManager] DEADLOCK DETECTED: Node-{holder} -> '{resource}' "
                        f"(held by Node-{owner}) would close a cycle. Aborting newer request."
                    )
                    return triage_pb2.LockReply(granted=False, message="deadlock detected")

                self.wait_for[holder] = resource
                print(
                    f"[LockManager] Node-{holder} WAITING for '{resource}' "
                    f"(held by Node-{owner})"
                )

            while True:
                with self.mutex:
                    owner = self.locks.get(resource)
                    if owner is None:
                        self.locks[resource] = holder
                        self.wait_for.pop(holder, None)
                        return triage_pb2.LockReply(granted=True, message="granted after wait")

                cond.wait(timeout=1)

    def ReleaseLock(self, request, context):
        resource = request.resource_id
        holder = request.holder_id
        cond = self.conditions[resource]

        with cond:
            with self.mutex:
                if self.locks.get(resource) == holder:
                    self.locks[resource] = None
            cond.notify_all()

        return triage_pb2.LockReply(granted=True, message="released")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    triage_pb2_grpc.add_LockServiceServicer_to_server(LockManager(), server)
    server.add_insecure_port("localhost:60100")
    server.start()

    print(f"LockManager started on localhost:60100 (deadlock detection = {DETECT})")

    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()