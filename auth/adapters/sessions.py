from uuid import UUID
from typing import Optional
from typing import Any
from typing import override
from datetime import datetime, timezone, timedelta
from json import dumps, loads
from dataclasses import dataclass
from auth.domain.models import User
from auth.domain.ports import Sessions as Collection
from auth.adapters.setup import UnitOfWork

@dataclass
class Session:
    id: UUID
    payload: dict[str, Any]
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return self.expires_at < datetime.now(tz=timezone.utc)
    
    @property
    def expires_in(self) -> int:
        return int((self.expires_at - datetime.now(tz=timezone.utc)).total_seconds())


class Sessions(Collection):
    def __init__(self, uow: UnitOfWork, user: Optional[User] = None):
        self.user = user
        self.uow = uow

    @override
    def create(self, id: UUID, payload: dict[str, Any], expires_at: datetime) -> Session:
        return Session(id=id, payload=payload, expires_at=expires_at)

    @override
    async def put(self, session: Session):
        assert self.user is not None, 'User is required to put session'
        if not session.is_expired:
            await self.uow.redis.set(f'{str(self.user.id)}:{str(session.id)}', str(session.id), ex=session.expires_in)
            await self.uow.redis.hset('session', f'{str(self.user.id)}:{str(session.id)}', dumps(session.payload))

    @override
    async def get(self, id: UUID) -> Optional[Session]:         
        async for key in self.uow.redis.scan_iter(match=f'*:{str(id)}', count=1):
            payload = await self.uow.redis.hget('session', key)
            expires_in = await self.uow.redis.ttl(key)
            expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)
            return Session(id=id, payload=loads(payload), expires_at=expires_at) if expires_in > 0 else None
    
    @override
    async def remove(self, session: Session):
        async for key in self.uow.redis.scan_iter(match=f'*:{str(session.id)}', count=1):
            await self.uow.redis.delete(key)

    @override
    async def list(self) -> list[Session]:
        assert self.user is not None, 'User is required to list sessions'
        sessions = []
        async for key in self.uow.redis.scan_iter(match=f'{str(self.user.id)}:*'):
            id = await self.uow.redis.get(key)
            payload = await self.uow.redis.hget('session', key)
            expires_in = await self.uow.redis.ttl(key)
            if expires_in > 0:
                expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)
                sessions.append(Session(id=UUID(bytes(id).decode()), payload=loads(payload), expires_at=expires_at))
        return sessions

    @override
    async def clear(self):
        assert self.user is not None, 'User is required to clear sessions'
        async for key in self.uow.redis.scan_iter(match=f'{str(self.user.id)}:*'):
            await self.uow.redis.delete(key)