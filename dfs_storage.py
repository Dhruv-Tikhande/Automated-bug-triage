"""Storage node for Experiment 11. Run with node number 1, 2, or 3."""
import hashlib
import os
import re
import sys
import threading
import time
from concurrent import futures

import grpc

import dfs_pb2
import dfs_pb2_grpc
import net_config

HEARTBEAT_INTERVAL = 2.0


class StorageServicer(dfs_pb2_grpc.DfsStorageServiceServicer):
    def __init__(self, node_id, directory):
        self.node_id = node_id
        self.directory = directory
        os.makedirs(directory, exist_ok=True)

    def _path(self, chunk_id):
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", chunk_id)
        if safe_id in {"", ".", ".."}:
            raise ValueError("invalid chunk id")
        return os.path.join(self.directory, safe_id)

    def PutChunk(self, request, context):
        digest = hashlib.sha256(request.data).hexdigest()
        if digest != request.sha256:
            print(f"[{self.node_id}] REJECTED {request.chunk_id}: checksum mismatch", flush=True)
            return dfs_pb2.DfsAck(ok=False, message="checksum mismatch")
        try:
            path = self._path(request.chunk_id)
        except ValueError as error:
            return dfs_pb2.DfsAck(ok=False, message=str(error))
        with open(path + ".tmp", "wb") as stream:
            stream.write(request.data)
        os.replace(path + ".tmp", path)
        print(f"[{self.node_id}] stored {request.chunk_id} ({len(request.data)} bytes)", flush=True)
        return dfs_pb2.DfsAck(ok=True, message="stored")

    def GetChunk(self, request, context):
        try:
            path = self._path(request.chunk_id)
        except ValueError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid chunk id")
        if not os.path.isfile(path):
            context.abort(grpc.StatusCode.NOT_FOUND, "chunk not found")
        with open(path, "rb") as stream:
            data = stream.read()
        print(f"[{self.node_id}] served {request.chunk_id} ({len(data)} bytes)", flush=True)
        return dfs_pb2.DfsChunkData(chunk_id=request.chunk_id, data=data,
                                    sha256=hashlib.sha256(data).hexdigest())


def heartbeat_loop(node_id, address):
    metadata_address = net_config.resolve("dfs-meta")
    reachable = None
    while True:
        try:
            with grpc.insecure_channel(metadata_address) as channel:
                stub = dfs_pb2_grpc.DfsMetadataServiceStub(channel)
                stub.Heartbeat(dfs_pb2.DfsNodeInfo(node_id=node_id, address=address), timeout=2)
            if reachable is not True:
                print(f"[{node_id}] connected to metadata server at {metadata_address}", flush=True)
            reachable = True
        except grpc.RpcError:
            if reachable is not False:
                print(f"[{node_id}] metadata server unreachable, will keep retrying", flush=True)
            reachable = False
        time.sleep(HEARTBEAT_INTERVAL)


def serve(node_num):
    if node_num not in {"1", "2", "3"}:
        raise SystemExit("usage: python dfs_storage.py <1|2|3>")
    node_id = f"store-{node_num}"
    address = net_config.resolve(f"dfs-store-{node_num}")
    port = address.rsplit(":", 1)[1]
    directory = os.path.join("dfs_data", node_id)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    dfs_pb2_grpc.add_DfsStorageServiceServicer_to_server(
        StorageServicer(node_id, directory), server)
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    print(f"DFS storage node {node_id} listening on {address}, "
          f"keeping chunks in {directory}/", flush=True)
    threading.Thread(target=heartbeat_loop, args=(node_id, address), daemon=True).start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve(sys.argv[1] if len(sys.argv) > 1 else "")
