from app.db.services.crud_audio import CRUDAudio, audio_crud
from app.db.services.crud_client import CRUDClient, client_crud
from app.db.services.crud_ticket import CRUDTicket, ticket_crud

__all__ = [
    "CRUDAudio",
    "CRUDClient",
    "CRUDTicket",
    "audio_crud",
    "client_crud",
    "ticket_crud",
]
