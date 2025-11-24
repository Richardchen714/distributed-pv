# test_raft_addsecret.py
import grpc
import argparse
from crypto_utils import CryptoUtils
import vault_pb2
import vault_pb2_grpc

GATEWAY_ADDRESS = "localhost:50050"
MASTER_PASSWORD = "my-super-secret-password"
DEFAULT_USER_ID = "user_alice"


class VaultClient:
    def __init__(self, gateway_address=GATEWAY_ADDRESS, user_id=DEFAULT_USER_ID, master_password=MASTER_PASSWORD):
        self.gateway_address = gateway_address
        self.user_id = user_id
        self.crypto = CryptoUtils(master_password)

    def add_secret(self, secret_name: str, secret_value: str):
        """Minimal functional test: Add only for Raft demo"""
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
                print(f"✓ SUCCESS: Added secret '{secret_name}'")
                print("  (Check Raft logs to confirm replication & apply)")

            except grpc.RpcError as e:
                print(f"✗ gRPC Error: {e.details()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a secret via Raft for demo")
    parser.add_argument("--name", "-n", type=str, help="Secret name")
    parser.add_argument("--value", "-v", type=str, help="Secret value")
    parser.add_argument("--user", "-u", default=DEFAULT_USER_ID, help="User ID")
    args = parser.parse_args()

    client = VaultClient(user_id=args.user)

    if args.name and args.value:
        client.add_secret(args.name, args.value)
    else:
        print("=" * 60)
        print("PASSWORD VAULT - ADD SECRET ONLY TEST (Interactive Mode)")
        print("=" * 60)

        while True:
            name = input("Enter secret name (or 'exit'): ").strip()
            if name.lower() == "exit":
                break
            value = input("Enter secret value: ").strip()
            client.add_secret(name, value)

    print("=" * 60)
    print("Finished. Check Docker Raft logs to verify replication!")
    print("=" * 60)
