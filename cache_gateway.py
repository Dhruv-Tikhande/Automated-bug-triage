import json
import sys

import grpc
import redis

import triage_pb2
import triage_pb2_grpc


REDIS_HOST = "localhost"
REDIS_PORT = 6379
CACHE_TTL_SECONDS = 10
BACKEND_SERVICE_ADDR = "localhost:50051"

FRESH_KEY_PREFIX = "fresh:triage:"
STALE_KEY_PREFIX = "stale:triage:"


BUG_REPORTS = {
    1: {
        "bug_title": "App crashes on login",
        "bug_description": (
            "The application crashes immediately when the user "
            "clicks the login button on Android."
        ),
    },
}


def get_redis():
    """Create a short-timeout Redis client for every gateway request."""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


def fetch_from_backend(bug_id):
    """Call the existing BugTriage gRPC service directly."""
    report = BUG_REPORTS.get(bug_id)

    if report is None:
        raise ValueError(f"Unknown demo bug ID: {bug_id}")

    with grpc.insecure_channel(BACKEND_SERVICE_ADDR) as channel:
        stub = triage_pb2_grpc.BugTriageStub(channel)

        response = stub.AnalyzeBug(
            triage_pb2.BugRequest(
                bug_title=report["bug_title"],
                bug_description=report["bug_description"],
                lamport_time=1,
            ),
            timeout=2,
        )

    return {
        "bug_id": bug_id,
        "predicted_priority": response.predicted_priority,
        "predicted_severity": response.predicted_severity,
        "suggested_assignee": response.suggested_assignee,
        "lamport_time": response.lamport_time,
    }


def get_triage_result(bug_id):
    fresh_key = f"{FRESH_KEY_PREFIX}{bug_id}"
    stale_key = f"{STALE_KEY_PREFIX}{bug_id}"

    try:
        redis_client = get_redis()
        cached = redis_client.get(fresh_key)

        if cached:
            print(f"[Gateway] CACHE HIT for bug {bug_id}")
            return json.loads(cached), "cache-hit"

        print(f"[Gateway] CACHE MISS for bug {bug_id} -- querying backend")

    except redis.exceptions.RedisError as error:
        print(
            f"[Gateway] REDIS UNAVAILABLE ({error}) "
            "-- falling back to backend directly"
        )
        redis_client = None

    try:
        data = fetch_from_backend(bug_id)
        print(f"[Gateway] Fetched bug {bug_id} from BACKEND")

        if redis_client is not None:
            try:
                redis_client.set(
                    fresh_key,
                    json.dumps(data),
                    ex=CACHE_TTL_SECONDS,
                )
                redis_client.set(
                    stale_key,
                    json.dumps(data),
                )
                print("[Gateway] Stored fresh and stale cache entries")

            except redis.exceptions.RedisError:
                print(
                    "[Gateway] Redis write failed, "
                    "continuing without caching this result"
                )

        return data, "backend"

    except grpc.RpcError as error:
        print(
            f"[Gateway] BACKEND UNAVAILABLE ({error.code()}) "
            "-- checking for stale cache"
        )

        if redis_client is not None:
            try:
                stale = redis_client.get(stale_key)

                if stale:
                    print(
                        f"[Gateway] Serving STALE cached copy "
                        f"for bug {bug_id}"
                    )
                    return json.loads(stale), "stale-fallback"

            except redis.exceptions.RedisError:
                pass

        raise RuntimeError(
            f"Bug {bug_id} unavailable: both backend and cache failed"
        )


if __name__ == "__main__":
    bug_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    result, source = get_triage_result(bug_id)

    print(f"\nResult (source={source}):")
    print(json.dumps(result, indent=2))