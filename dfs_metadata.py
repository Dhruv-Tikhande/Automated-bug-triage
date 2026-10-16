"""Metadata coordinator for Experiment 11's replicated distributed file store."""
import json
import os
import threading
import time
from concurrent import futures

import grpc

import dfs_pb2
import dfs_pb2_grpc
import net_config

REPLICATION_FACTOR = 2
HEARTBEAT_TIMEOUT = 6.0
STATE_FILE = os.environ.get("DFS_METADATA_FILE", "dfs_data/metadata.json")


class MetadataServicer(dfs_pb2_grpc.DfsMetadataServiceServicer):
    def __init__(self):
        self.lock = threading.RLock()
        self.clock = 0
        self.addresses = {}
        self.last_seen = {}
        self.files = {}
        self._load()

    def log(self, message):
        print(f"[meta t={self.clock:>3}] {message}", flush=True)

    def _tick(self):
        self.clock += 1
        return self.clock

    def _update(self, received):
        self.clock = max(self.clock, received) + 1
        return self.clock

    def _load(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, encoding="utf-8") as stream:
                data = json.load(stream)
            self.files = data.get("files", {})
            self.addresses = data.get("addresses", {})
            self.clock = data.get("clock", 0)
            print(f"Loaded {len(self.files)} file(s) from {STATE_FILE}", flush=True)

    def _save(self):
        parent = os.path.dirname(STATE_FILE)
        if parent:
            os.makedirs(parent, exist_ok=True)
        temp_path = STATE_FILE + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as stream:
            json.dump({"clock": self.clock, "addresses": self.addresses,
                       "files": self.files}, stream)
        os.replace(temp_path, STATE_FILE)

    def _alive(self, node_id):
        seen = self.last_seen.get(node_id)
        return seen is not None and time.time() - seen <= HEARTBEAT_TIMEOUT

    def _chunk_counts(self):
        counts = {}
        for record in self.files.values():
            for chunk in record["chunks"]:
                for node_id in chunk["nodes"]:
                    counts[node_id] = counts.get(node_id, 0) + 1
        return counts

    def _file_info(self, filename, record):
        chunks = []
        for chunk in record["chunks"]:
            nodes = sorted(chunk["nodes"], key=lambda n: (not self._alive(n), n))
            chunks.append(dfs_pb2.DfsChunkPlan(
                index=chunk["index"], chunk_id=chunk["chunk_id"],
                sha256=chunk["sha256"], node_ids=nodes,
                addresses=[self.addresses.get(node_id, "") for node_id in nodes],
                alive=[self._alive(node_id) for node_id in nodes]))
        return dfs_pb2.DfsFileInfo(
            found=True, filename=filename, version=record["version"],
            size=record["size"], sha256=record["sha256"], chunks=chunks)

    def Heartbeat(self, request, context):
        with self.lock:
            is_new = request.node_id not in self.last_seen
            self.last_seen[request.node_id] = time.time()
            if self.addresses.get(request.node_id) != request.address:
                self.addresses[request.node_id] = request.address
                self._save()
            if is_new:
                self.log(f"Node {request.node_id} registered at {request.address}")
        return dfs_pb2.DfsAck(ok=True, message="ok")

    def AllocateFile(self, request, context):
        with self.lock:
            self._update(request.lamport_timestamp)
            if not request.filename or request.num_chunks < 1:
                return dfs_pb2.DfsAllocateReply(ok=False,
                    message="filename and positive chunk count are required",
                    lamport_timestamp=self.clock)
            live = [node for node in self.addresses if self._alive(node)]
            if not live:
                return dfs_pb2.DfsAllocateReply(ok=False,
                    message="no live storage nodes", lamport_timestamp=self.clock)
            version = self._tick()
            replica_count = min(REPLICATION_FACTOR, len(live))
            counts = self._chunk_counts()
            load = {node: counts.get(node, 0) for node in live}
            plan = []
            for index in range(request.num_chunks):
                chosen = sorted(live, key=lambda node: (load[node], node))[:replica_count]
                for node in chosen:
                    load[node] += 1
                plan.append(dfs_pb2.DfsChunkPlan(
                    index=index,
                    chunk_id=f"{request.filename}.v{version}.c{index}",
                    node_ids=chosen,
                    addresses=[self.addresses[node] for node in chosen]))
            self.log(f"Allocated '{request.filename}' v{version}: "
                     f"{request.num_chunks} chunk(s), {replica_count} replica(s) each")
            return dfs_pb2.DfsAllocateReply(ok=True, message="allocated",
                version=version, plan=plan, lamport_timestamp=self.clock)

    def CommitFile(self, request, context):
        with self.lock:
            if (not request.filename or request.size < 0 or not request.sha256
                    or not request.chunks or any(not chunk.node_ids for chunk in request.chunks)):
                return dfs_pb2.DfsCommitReply(ok=False,
                    message="file metadata and at least one stored replica per chunk are required",
                    lamport_timestamp=self.clock)
            ordered = sorted(request.chunks, key=lambda chunk: chunk.index)
            if [chunk.index for chunk in ordered] != list(range(len(ordered))):
                return dfs_pb2.DfsCommitReply(ok=False, message="chunk indexes must be contiguous",
                                              lamport_timestamp=self.clock)
            self.files[request.filename] = {
                "version": request.version, "size": request.size,
                "sha256": request.sha256,
                "chunks": [{"index": chunk.index, "chunk_id": chunk.chunk_id,
                            "sha256": chunk.sha256,
                            "nodes": list(dict.fromkeys(chunk.node_ids))}
                           for chunk in ordered],
            }
            timestamp = self._tick()
            self._save()
            self.log(f"Committed '{request.filename}' v{request.version} ({request.size} bytes)")
            return dfs_pb2.DfsCommitReply(ok=True, message="committed",
                                          lamport_timestamp=timestamp)

    def GetFileInfo(self, request, context):
        with self.lock:
            record = self.files.get(request.filename)
            return self._file_info(request.filename, record) if record else dfs_pb2.DfsFileInfo(
                found=False, filename=request.filename)

    def ClusterStatus(self, request, context):
        with self.lock:
            counts = self._chunk_counts()
            nodes = [dfs_pb2.DfsNodeStatus(node_id=node, address=address,
                alive=self._alive(node), chunk_count=counts.get(node, 0))
                for node, address in sorted(self.addresses.items())]
            files = [self._file_info(name, record)
                     for name, record in sorted(self.files.items())]
            return dfs_pb2.DfsStatusReply(nodes=nodes, files=files)

    def AddReplica(self, request, context):
        with self.lock:
            record = self.files.get(request.filename)
            if record is None:
                return dfs_pb2.DfsAck(ok=False, message="unknown file")
            if request.node_id not in self.addresses:
                return dfs_pb2.DfsAck(ok=False, message="unknown storage node")
            for chunk in record["chunks"]:
                if chunk["index"] == request.chunk_index:
                    if request.node_id not in chunk["nodes"]:
                        chunk["nodes"].append(request.node_id)
                        self._save()
                    return dfs_pb2.DfsAck(ok=True, message="replica recorded")
            return dfs_pb2.DfsAck(ok=False, message="unknown chunk")

    def monitor(self):
        reported = {}
        while True:
            time.sleep(1)
            with self.lock:
                for node_id in list(self.addresses):
                    alive = self._alive(node_id)
                    previous = reported.get(node_id)
                    reported[node_id] = alive
                    if previous is not None and previous != alive:
                        state = "BACK UP" if alive else "DOWN (no heartbeat)"
                        self.log(f"Node {node_id} is {state}")


def serve():
    address = net_config.resolve("dfs-meta")
    port = address.rsplit(":", 1)[1]
    servicer = MetadataServicer()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    dfs_pb2_grpc.add_DfsMetadataServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    print(f"DFS metadata server listening on {address} "
          f"(replication factor {REPLICATION_FACTOR})", flush=True)
    threading.Thread(target=servicer.monitor, daemon=True).start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()
