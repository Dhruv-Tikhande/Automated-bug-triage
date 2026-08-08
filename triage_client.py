import grpc

# Import generated classes
import triage_pb2
import triage_pb2_grpc
from lamport_clock import LamportClock

client_clock = LamportClock()

def run():
    # Connect to the ML Triage server
    print("Connecting to ML Triage Service...")

    with grpc.insecure_channel('localhost:50051') as channel:
        stub = triage_pb2_grpc.BugTriageStub(channel)

        request_time = client_clock.send_event()
        print("client Lamport time before request:",request_time)
        # Create a sample bug request
        bug_data = triage_pb2.BugRequest(
            bug_title="App crashes on login",
            bug_description="The application crash immediately when I click the login button on Android.",
            lamport_time = request_time
        )
        
        # Make the RPC call
        response = stub.AnalyzeBug(bug_data)

        final_time = client_clock.receive_event(response.lamport_time)
        print("Client Lamport time after response:", final_time)
        print("\n--- Triage Results Received ---")
        print(f"Priority: {response.predicted_priority}")
        print(f"Severity: {response.predicted_severity}")
        print(f"Assignee: {response.suggested_assignee}")
        print(f"Response Lamport time: {response.lamport_time}")

if __name__ == '__main__':
    run()