"""Command-line client for Experiment 11's distributed file store.

Usage: python dfs_client.py put <path> | get <filename> <output> | status
"""
import hashlib
import os
import sys

import grpc

import dfs_pb2
import dfs_pb2_grpc
import net_config

CHUNK_SIZE = int(os.environ.get("DFS_CHUNK_SIZE", 64 * 1024))
CLOCK_FILE = ".dfs_client_clock"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_clock():
    try:
        with open(CLOCK_FILE, encoding="ascii") as stream:
            return int(stream.read().strip())
    except (OSError, ValueError):
        return 0


def save_clock(value):
    with open(CLOCK_FILE, "w", encoding="ascii") as stream:
        stream.write(str(value))


def meta_channel():
    return grpc.insecure_channel(net_config.resolve("dfs-meta"))


def put(path):
    try:
        with open(path, "rb") as stream:
            data = stream.read()
    except OSError as error:
        print(f"Upload failed: {error}")
        return 1
    filename = os.path.basename(path)
    if not filename:
        print("Upload failed: path must name a file")
        return 1
    pieces = [data[i:i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)] or [b""]
    clock = load_clock() + 1
    try:
        with meta_channel() as channel:
            meta = dfs_pb2_grpc.DfsMetadataServiceStub(channel)
            allocation = meta.AllocateFile(dfs_pb2.DfsAllocateRequest(
                filename=filename, num_chunks=len(pieces),
                lamport_timestamp=clock), timeout=5)
            if not allocation.ok:
                print(f"Upload failed: {allocation.message}")
                return 1
            clock = max(clock, allocation.lamport_timestamp) + 1
            print(f"Allocated '{filename}' as version {allocation.version}: "
                  f"{len(data)} bytes in {len(pieces)} chunk(s)")
            committed = []
            for plan in allocation.plan:
                piece = pieces[plan.index]
                digest = sha256(piece)
                stored_on = []
                for node_id, address in zip(plan.node_ids, plan.addresses):
                    try:
                        with grpc.insecure_channel(address) as storage_channel:
                            ack = dfs_pb2_grpc.DfsStorageServiceStub(storage_channel).PutChunk(
                                dfs_pb2.DfsChunkData(chunk_id=plan.chunk_id,
                                    data=piece, sha256=digest), timeout=5)
                        if ack.ok:
                            stored_on.append(node_id)
                        else:
                            print(f" chunk {plan.index}: {node_id} refused ({ack.message})")
                    except grpc.RpcError as error:
                        print(f" chunk {plan.index}: {node_id} unreachable ({error.code().name})")
                if not stored_on:
                    print(f"Upload failed: chunk {plan.index} could not be stored on any node. "
                          "The file was not committed.")
                    return 1
                committed.append(dfs_pb2.DfsChunkPlan(index=plan.index,
                    chunk_id=plan.chunk_id, sha256=digest, node_ids=stored_on))
                print(f" chunk {plan.index}: stored on {', '.join(stored_on)}")
            result = meta.CommitFile(dfs_pb2.DfsCommitRequest(
                filename=filename, version=allocation.version, size=len(data),
                sha256=sha256(data), chunks=committed), timeout=5)
            clock = max(clock, result.lamport_timestamp) + 1
            save_clock(clock)
            if not result.ok:
                print(f"Commit failed: {result.message}")
                return 1
            print(f"Committed '{filename}' v{allocation.version}. "
                  f"Whole-file checksum {sha256(data)[:16]}...")
            return 0
    except grpc.RpcError as error:
        print(f"Could not reach the metadata server ({error.code().name}). "
              "Is dfs_metadata.py running?")
        return 1


def get(filename, out_path):
    try:
        with meta_channel() as channel:
            meta = dfs_pb2_grpc.DfsMetadataServiceStub(channel)
            info = meta.GetFileInfo(dfs_pb2.DfsFileQuery(filename=filename), timeout=5)
    except grpc.RpcError as error:
        print(f"Could not reach the metadata server ({error.code().name}). "
              "Is dfs_metadata.py running?")
        return 1
    if not info.found:
        print(f"No file called '{filename}' in the store.")
        return 1
    print(f"Reading '{filename}' v{info.version}: {info.size} bytes in "
          f"{len(info.chunks)} chunk(s)")
    parts = []
    for chunk in sorted(info.chunks, key=lambda item: item.index):
        content = None
        for node_id, address in zip(chunk.node_ids, chunk.addresses):
            if not address:
                continue
            try:
                with grpc.insecure_channel(address) as storage_channel:
                    reply = dfs_pb2_grpc.DfsStorageServiceStub(storage_channel).GetChunk(
                        dfs_pb2.DfsChunkId(chunk_id=chunk.chunk_id), timeout=3)
            except grpc.RpcError as error:
                print(f" chunk {chunk.index}: {node_id} unavailable ({error.code().name}), "
                      "trying next replica")
                continue
            if sha256(reply.data) != chunk.sha256:
                print(f" chunk {chunk.index}: {node_id} returned CORRUPT data, "
                      "trying next replica")
                continue
            content = reply.data
            print(f" chunk {chunk.index}: read from {node_id}")
            break
        if content is None:
            print(f"Read failed: no healthy replica for chunk {chunk.index}.")
            return 1
        parts.append(content)
    blob = b"".join(parts)
    if len(blob) != info.size or sha256(blob) != info.sha256:
        print("Read failed: the whole-file size or checksum does not match.")
        return 1
    try:
        with open(out_path, "wb") as stream:
            stream.write(blob)
    except OSError as error:
        print(f"Could not write output file: {error}")
        return 1
    print(f"OK: wrote {len(blob)} bytes to {out_path}, checksum verified.")
    return 0


def status():
    try:
        with meta_channel() as channel:
            reply = dfs_pb2_grpc.DfsMetadataServiceStub(channel).ClusterStatus(
                dfs_pb2.DfsStatusRequest(), timeout=5)
    except grpc.RpcError as error:
        print(f"Could not reach the metadata server ({error.code().name}). "
              "Is dfs_metadata.py running?")
        return 1
    print("Storage nodes:")
    for node in reply.nodes:
        state = "UP " if node.alive else "DOWN"
        print(f" {node.node_id} {state} {node.address} chunks held: {node.chunk_count}")
    print("Files:")
    if not reply.files:
        print(" (none)")
    for file_info in reply.files:
        print(f" {file_info.filename} v{file_info.version} {file_info.size} bytes "
              f"{len(file_info.chunks)} chunk(s)")
        for chunk in sorted(file_info.chunks, key=lambda item: item.index):
            where = ", ".join(f"{node}{'' if alive else ' (down)'}"
                               for node, alive in zip(chunk.node_ids, chunk.alive))
            print(f" chunk {chunk.index}: {where}")
    return 0


def main(args):
    if len(args) == 2 and args[0] == "put":
        return put(args[1])
    if len(args) == 3 and args[0] == "get":
        return get(args[1], args[2])
    if len(args) == 1 and args[0] == "status":
        return status()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
