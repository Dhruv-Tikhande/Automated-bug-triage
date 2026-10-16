"""Restore the configured replica count for chunks with healthy source copies."""
import hashlib

import grpc

import dfs_pb2
import dfs_pb2_grpc
import net_config

REPLICATION_FACTOR = 2


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def repair():
    try:
        with grpc.insecure_channel(net_config.resolve("dfs-meta")) as channel:
            metadata = dfs_pb2_grpc.DfsMetadataServiceStub(channel)
            status = metadata.ClusterStatus(dfs_pb2.DfsStatusRequest(), timeout=5)
            alive = {node.node_id: node.address for node in status.nodes if node.alive}
            print(f"Live nodes: {', '.join(sorted(alive)) or 'none'}")
            copied = 0
            problems = 0
            for file_info in status.files:
                for chunk in sorted(file_info.chunks, key=lambda item: item.index):
                    holders = [(node_id, address) for node_id, address, up
                               in zip(chunk.node_ids, chunk.addresses, chunk.alive) if up]
                    missing = REPLICATION_FACTOR - len(holders)
                    if missing <= 0:
                        continue
                    if not holders:
                        print(f" {file_info.filename} chunk {chunk.index}: NO live replica, "
                              "cannot repair")
                        problems += 1
                        continue
                    data = None
                    for _node_id, address in holders:
                        try:
                            with grpc.insecure_channel(address) as storage_channel:
                                reply = dfs_pb2_grpc.DfsStorageServiceStub(storage_channel).GetChunk(
                                    dfs_pb2.DfsChunkId(chunk_id=chunk.chunk_id), timeout=3)
                            if sha256(reply.data) == chunk.sha256:
                                data = reply.data
                                break
                        except grpc.RpcError:
                            continue
                    if data is None:
                        print(f" {file_info.filename} chunk {chunk.index}: no healthy copy to read from")
                        problems += 1
                        continue
                    targets = [node_id for node_id in sorted(alive)
                               if node_id not in chunk.node_ids]
                    repaired = 0
                    for target in targets:
                        try:
                            with grpc.insecure_channel(alive[target]) as storage_channel:
                                ack = dfs_pb2_grpc.DfsStorageServiceStub(storage_channel).PutChunk(
                                    dfs_pb2.DfsChunkData(chunk_id=chunk.chunk_id,
                                        data=data, sha256=chunk.sha256), timeout=5)
                            if not ack.ok:
                                continue
                            recorded = metadata.AddReplica(dfs_pb2.DfsReplicaUpdate(
                                filename=file_info.filename, chunk_index=chunk.index,
                                node_id=target), timeout=5)
                            if not recorded.ok:
                                print(f" {file_info.filename} chunk {chunk.index}: "
                                      f"stored on {target}, metadata update failed ({recorded.message})")
                                problems += 1
                                continue
                            print(f" {file_info.filename} chunk {chunk.index}: copied to {target}")
                            copied += 1
                            repaired += 1
                            if repaired == missing:
                                break
                        except grpc.RpcError as error:
                            print(f" {file_info.filename} chunk {chunk.index}: could not copy to "
                                  f"{target} ({error.code().name})")
                            problems += 1
                    if repaired < missing:
                        problems += 1
            print(f"Repair finished: {copied} chunk copy(ies) made, {problems} problem(s).")
            return 0 if problems == 0 else 1
    except grpc.RpcError as error:
        print(f"Could not reach the metadata server ({error.code().name}).")
        return 1


if __name__ == "__main__":
    raise SystemExit(repair())
