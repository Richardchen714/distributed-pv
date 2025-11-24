# secret_management_service.py
# Microservice responsible for: Add Secret, Update Secret, Delete Secret
from concurrent import futures
import grpc
import os
import json
import threading
from datetime import datetime

import json
import uuid
from vault_pb2 import AddSecretResponse
from raft.raft_integration import propose_operation
import vault_pb2
import vault_pb2_grpc
import shared_data

RAFT_NODE_ADDR = os.getenv("RAFT_NODE_ADDR", "raft-node1:7001")
# Replication service addresses
REPLICATION_SERVICE_ADDRS = os.environ.get("REPLICATION_NODES", "").split(',')

def replicate_secret(secret_id, user_id, secret_name, data, created_at):
    """Replicate secret to other nodes via Replication Service"""
    for addr in REPLICATION_SERVICE_ADDRS:
        if not addr:
            continue
        try:
            with grpc.insecure_channel(addr) as channel:
                stub = vault_pb2_grpc.ReplicationServiceStub(channel)
                request = vault_pb2.ReplicateSecretRequest(
                    secret_id=secret_id,
                    user_id=user_id,
                    secret_name=secret_name,
                    data=data,
                    created_at=created_at
                )
                stub.ReplicateSecret(request, timeout=2)
                print(f"[SecretManagement] Replicated secret {secret_id} to {addr}")
        except grpc.RpcError as e:
            print(f"[SecretManagement] Failed to replicate to {addr}: {e}")

def replicate_update(secret_id, data, updated_at):
    """Replicate secret update to other nodes"""
    for addr in REPLICATION_SERVICE_ADDRS:
        if not addr:
            continue
        try:
            with grpc.insecure_channel(addr) as channel:
                stub = vault_pb2_grpc.ReplicationServiceStub(channel)
                request = vault_pb2.ReplicateUpdateRequest(
                    secret_id=secret_id,
                    data=data,
                    updated_at=updated_at
                )
                stub.ReplicateUpdate(request, timeout=2)
                print(f"[SecretManagement] Replicated update {secret_id} to {addr}")
        except grpc.RpcError as e:
            print(f"[SecretManagement] Failed to replicate update to {addr}: {e}")

def replicate_deletion(secret_id):
    """Replicate secret deletion to other nodes"""
    for addr in REPLICATION_SERVICE_ADDRS:
        if not addr:
            continue
        try:
            with grpc.insecure_channel(addr) as channel:
                stub = vault_pb2_grpc.ReplicationServiceStub(channel)
                request = vault_pb2.ReplicateDeletionRequest(secret_id=secret_id)
                stub.ReplicateDeletion(request, timeout=2)
                print(f"[SecretManagement] Replicated deletion {secret_id} to {addr}")
        except grpc.RpcError as e:
            print(f"[SecretManagement] Failed to replicate deletion to {addr}: {e}")

class SecretManagementServiceImpl(vault_pb2_grpc.SecretManagementServiceServicer):

    # def AddSecret(self, request, context):
    #     """Requirement 1: Add Secret"""
    #     import uuid

    #     secret_id = str(uuid.uuid4())
    #     timestamp = datetime.utcnow().isoformat()

    #     # Store secret locally
    #     shared_data.set_secret(secret_id, {
    #         'user_id': request.user_id,
    #         'secret_name': request.secret_name,
    #         'data': request.data,
    #         'created_at': timestamp,
    #         'updated_at': timestamp
    #     })

    #     print(f"[SecretManagement] Added secret {secret_id} for user {request.user_id}")

    #     # Replicate in background
    #     threading.Thread(
    #         target=replicate_secret,
    #         args=(secret_id, request.user_id, request.secret_name, request.data, timestamp)
    #     ).start()

    #     return vault_pb2.AddSecretResponse(
    #         secret_id=secret_id,
    #         message="Secret added successfully",
    #         success=True
    #     )
    def AddSecret(self, request, context):
        """Add Secret via Raft consensus"""

        operation = json.dumps({
            "type": "add_secret",
            "user_id": request.user_id,
            "secret_name": request.secret_name,
            "data": request.data,
        })

        success, result = propose_operation(operation)  

        if not success:
            return AddSecretResponse(
                secret_id="",
                message=f"Operation rejected: {result}",
                success=False
            )

        print(f"[SecretManagement] Secret committed at Raft index {result}")

        return AddSecretResponse(
            secret_id=str(result),
            message="Secret added via Raft replication",
            success=True
        )


    def UpdateSecret(self, request, context):
        """Requirement 3: Update Secret"""
        secret_id = request.secret_id

        secret = shared_data.get_secret(secret_id)
        if not secret:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Secret not found")
            return vault_pb2.UpdateSecretResponse(
                secret_id=secret_id,
                message="Secret not found",
                success=False
            )

        # Verify ownership
        if secret['user_id'] != request.user_id:
            context.set_code(grpc.StatusCode.PERMISSION_DENIED)
            context.set_details("Not authorized to update this secret")
            return vault_pb2.UpdateSecretResponse(
                secret_id=secret_id,
                message="Not authorized",
                success=False
            )

        # Update secret
        timestamp = datetime.utcnow().isoformat()
        secret['data'] = request.data
        secret['updated_at'] = timestamp
        shared_data.set_secret(secret_id, secret)

        print(f"[SecretManagement] Updated secret {secret_id}")

        # Replicate update
        threading.Thread(
            target=replicate_update,
            args=(secret_id, request.data, timestamp)
        ).start()

        return vault_pb2.UpdateSecretResponse(
            secret_id=secret_id,
            message="Secret updated successfully",
            success=True
        )

    def DeleteSecret(self, request, context):
        """Requirement 3: Delete Secret"""
        secret_id = request.secret_id

        secret = shared_data.get_secret(secret_id)
        if not secret:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Secret not found")
            return vault_pb2.DeleteSecretResponse(
                secret_id=secret_id,
                message="Secret not found",
                success=False
            )

        # Verify ownership
        if secret['user_id'] != request.user_id:
            context.set_code(grpc.StatusCode.PERMISSION_DENIED)
            context.set_details("Not authorized to delete this secret")
            return vault_pb2.DeleteSecretResponse(
                secret_id=secret_id,
                message="Not authorized",
                success=False
            )

        # Delete secret
        shared_data.delete_secret(secret_id)
        print(f"[SecretManagement] Deleted secret {secret_id}")

        # Replicate deletion
        threading.Thread(
            target=replicate_deletion,
            args=(secret_id,)
        ).start()

        return vault_pb2.DeleteSecretResponse(
            secret_id=secret_id,
            message="Secret deleted successfully",
            success=True
        )

def serve():
    port = os.environ.get("PORT", "50051")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    vault_pb2_grpc.add_SecretManagementServiceServicer_to_server(
        SecretManagementServiceImpl(), server
    )
    server.add_insecure_port(f'[::]:{port}')
    print(f"[SecretManagement] Service started on port {port}")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
