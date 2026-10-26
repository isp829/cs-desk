import os

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


def load_secrets() -> str:
    vault_url = os.environ.get("KEY_VAULT_URL")
    if not vault_url:
        raise RuntimeError("KEY_VAULT_URL 환경변수가 필요합니다")

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)
    github_token = client.get_secret("GITHUB-TOKEN").value
    admin_password = client.get_secret("ADMIN-PASSWORD").value
    if not github_token or not admin_password:
        raise RuntimeError("Key Vault 필수 시크릿을 읽지 못했습니다")
    os.environ["GITHUB_TOKEN"] = github_token
    return admin_password