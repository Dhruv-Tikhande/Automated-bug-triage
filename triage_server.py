import grpc
from concurrent import futures
import time

# Import generated classes
import triage_pb2
import triage_pb2_grpc
from lamport_clock import LamportClock

server_clock = LamportClock()

class BugTriageServicer(triage_pb2_grpc.BugTriageServicer):
    def AnalyzeBug(self, request, context):
        received_time = server_clock.receive_event(request.lamport_time)
        print(f"Received Bug for Triage: {request.bug_title}")
        print("Server Lamport time after receive:", received_time)
        
        # Simulating your Bayesian Network and ANN predictions
        priority = "High" if "crash" in request.bug_description.lower() else "Medium"
        severity = "Critical" if "crash" in request.bug_description.lower() else "Major"
        assignee = "Senior Backend Dev" if "crash" in request.bug_description.lower() else "Frontend Dev"

        response_time = server_clock.send_event()
        print("Server Lamport time before response:", response_time)

        return triage_pb2.TriageResponse(
            predicted_priority=priority,
            predicted_severity=severity,
            suggested_assignee=assignee,
            lamport_time = response_time
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    triage_pb2_grpc.add_BugTriageServicer_to_server(BugTriageServicer(), server)
    
    print("ML Triage Service Started on Port 50051...")
    server.add_insecure_port('[::]:50051')
    server.start()
    
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()