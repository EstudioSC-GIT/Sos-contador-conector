import os

from dotenv import load_dotenv

from .client import SOSContadorClient


def client_from_env(dotenv_path: str | None = None) -> SOSContadorClient:
    load_dotenv(dotenv_path)
    usuario = os.environ["SOS_USUARIO"]
    password = os.environ["SOS_PASSWORD"]
    return SOSContadorClient(usuario=usuario, password=password)
