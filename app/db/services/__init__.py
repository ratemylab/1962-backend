from app.db.services.crud_admin import CRUDAdmin, admin_crud
from app.db.services.crud_audio import CRUDAudio, audio_crud
from app.db.services.crud_client import CRUDClient, client_crud
from app.db.services.crud_refresh_token import CRUDRefreshToken, refresh_token_crud
from app.db.services.crud_ticket import CRUDTicket, ticket_crud

__all__ = [
    "CRUDAdmin",
    "CRUDAudio",
    "CRUDClient",
    "CRUDRefreshToken",
    "CRUDTicket",
    "admin_crud",
    "audio_crud",
    "client_crud",
    "refresh_token_crud",
    "ticket_crud",
]
