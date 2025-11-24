# microservices_client.py
# Client for interacting with the microservices-based distributed password vault
import grpc
import uuid
from crypto_utils import CryptoUtils

import vault_pb2
import vault_pb2_grpc

# Configuration - Connect to API Gateway
GATEWAY_ADDRESS = "localhost:50050"
MASTER_PASSWORD = "my-super-secret-password"
DEFAULT_USER_ID = "user_alice"

class VaultClient:
    def __init__(self, gateway_address=GATEWAY_ADDRESS, user_id=DEFAULT_USER_ID, master_password=MASTER_PASSWORD):
        self.gateway_address = gateway_address
        self.user_id = user_id
        self.crypto = CryptoUtils(master_password)

    def add_secret(self, secret_name: str, secret_value: str):
        """Requirement 1: Add Secret"""
        encrypted_data = self.crypto.encrypt(secret_value)

        with grpc.insecure_channel(self.gateway_address) as channel:
            stub = vault_pb2_grpc.SecretManagementServiceStub(channel)
            request = vault_pb2.AddSecretRequest(
                user_id=self.user_id,
                secret_name=secret_name,
                data=encrypted_data
            )
            try:
                response = stub.AddSecret(request)
                if response.success:
                    print(f"✓ Successfully added secret '{secret_name}'")
                    print(f"  Secret ID: {response.secret_id}")
                    return response.secret_id
                else:
                    print(f"✗ Failed to add secret: {response.message}")
                    return None
            except grpc.RpcError as e:
                print(f"✗ Error adding secret: {e.details()}")
                return None

    def retrieve_secret(self, secret_id: str):
        """Requirement 2: Retrieve Secret"""
        with grpc.insecure_channel(self.gateway_address) as channel:
            stub = vault_pb2_grpc.SecretRetrievalServiceStub(channel)
            request = vault_pb2.RetrieveSecretRequest(
                user_id=self.user_id,
                secret_id=secret_id
            )
            try:
                response = stub.RetrieveSecret(request)
                if response.success:
                    decrypted_value = self.crypto.decrypt(response.data)
                    if decrypted_value:
                        print(f"✓ Retrieved secret ID: {secret_id}")
                        print(f"  Decrypted Value: '{decrypted_value}'")
                        return decrypted_value
                    else:
                        print(f"✗ Failed to decrypt secret")
                        return None
                else:
                    print(f"✗ Failed to retrieve secret")
                    return None
            except grpc.RpcError as e:
                print(f"✗ Error retrieving secret: {e.details()}")
                return None

    def update_secret(self, secret_id: str, new_value: str):
        """Requirement 3: Update Secret"""
        encrypted_data = self.crypto.encrypt(new_value)

        with grpc.insecure_channel(self.gateway_address) as channel:
            stub = vault_pb2_grpc.SecretManagementServiceStub(channel)
            request = vault_pb2.UpdateSecretRequest(
                user_id=self.user_id,
                secret_id=secret_id,
                data=encrypted_data
            )
            try:
                response = stub.UpdateSecret(request)
                if response.success:
                    print(f"✓ Successfully updated secret {secret_id}")
                    return True
                else:
                    print(f"✗ Failed to update secret: {response.message}")
                    return False
            except grpc.RpcError as e:
                print(f"✗ Error updating secret: {e.details()}")
                return False

    def delete_secret(self, secret_id: str):
        """Requirement 3: Delete Secret"""
        with grpc.insecure_channel(self.gateway_address) as channel:
            stub = vault_pb2_grpc.SecretManagementServiceStub(channel)
            request = vault_pb2.DeleteSecretRequest(
                user_id=self.user_id,
                secret_id=secret_id
            )
            try:
                response = stub.DeleteSecret(request)
                if response.success:
                    print(f"✓ Successfully deleted secret {secret_id}")
                    return True
                else:
                    print(f"✗ Failed to delete secret: {response.message}")
                    return False
            except grpc.RpcError as e:
                print(f"✗ Error deleting secret: {e.details()}")
                return False

    def list_secrets(self):
        """Requirement 4: List Secrets"""
        with grpc.insecure_channel(self.gateway_address) as channel:
            stub = vault_pb2_grpc.SecretRetrievalServiceStub(channel)
            request = vault_pb2.ListSecretsRequest(user_id=self.user_id)
            try:
                response = stub.ListSecrets(request)
                print(f"✓ Found {response.total_count} secret(s):")
                for secret_meta in response.secrets:
                    shared_indicator = " [SHARED]" if secret_meta.is_shared else ""
                    print(f"  - {secret_meta.secret_name}{shared_indicator}")
                    print(f"    ID: {secret_meta.secret_id}")
                    print(f"    Created: {secret_meta.created_at}")
                    print(f"    Updated: {secret_meta.updated_at}")
                return response.secrets
            except grpc.RpcError as e:
                print(f"✗ Error listing secrets: {e.details()}")
                return []

    def share_secret(self, secret_id: str, target_user_id: str):
        """Requirement 5: Share Secret"""
        with grpc.insecure_channel(self.gateway_address) as channel:
            stub = vault_pb2_grpc.AccessControlServiceStub(channel)
            request = vault_pb2.ShareSecretRequest(
                owner_id=self.user_id,
                secret_id=secret_id,
                target_user_id=target_user_id
            )
            try:
                response = stub.ShareSecret(request)
                if response.success:
                    print(f"✓ Successfully shared secret with {target_user_id}")
                    return True
                else:
                    print(f"✗ Failed to share secret: {response.message}")
                    return False
            except grpc.RpcError as e:
                print(f"✗ Error sharing secret: {e.details()}")
                return False


def demo_all_operations():
    """Demonstrate all 5 functional requirements"""
    print("=" * 60)
    print("Distributed Password Vault - Microservices Architecture")
    print("=" * 60)

    # Initialize client for Alice
    alice = VaultClient(user_id="user_alice")

    print("\n--- Requirement 1: Add Secret ---")
    db_password_id = alice.add_secret("Database Password", "P@ssw0rd123!")
    api_key_id = alice.add_secret("API Key", "sk-1234567890abcdef")

    if not db_password_id or not api_key_id:
        print("Failed to add secrets. Exiting.")
        return

    print("\n--- Requirement 2: Retrieve Secret ---")
    alice.retrieve_secret(db_password_id)

    print("\n--- Requirement 4: List Secrets ---")
    alice.list_secrets()

    print("\n--- Requirement 3: Update Secret ---")
    alice.update_secret(db_password_id, "NewP@ssw0rd456!")

    print("\n--- Requirement 2: Retrieve Updated Secret ---")
    alice.retrieve_secret(db_password_id)

    print("\n--- Requirement 5: Share Secret ---")
    alice.share_secret(api_key_id, "user_bob")

    # Create client for Bob to test shared access
    print("\n--- Bob accesses shared secret ---")
    bob = VaultClient(user_id="user_bob")
    bob.retrieve_secret(api_key_id)

    print("\n--- Bob lists his secrets (includes shared) ---")
    bob.list_secrets()

    print("\n--- Requirement 3: Delete Secret ---")
    alice.delete_secret(db_password_id)

    print("\n--- List secrets after deletion ---")
    alice.list_secrets()

    print("\n" + "=" * 60)
    print("All operations completed successfully!")
    print("=" * 60)


if __name__ == '__main__':
    demo_all_operations()
