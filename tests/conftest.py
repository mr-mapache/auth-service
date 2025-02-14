from pytest_asyncio import fixture
from uuid import UUID
from auth.settings import Settings
from auth.adapters.schemas import Schema
from auth.adapters.backend import Database, Cache, UnitOfWork
from auth.adapters.users import Users
from auth.adapters.accounts import Accounts
from auth.adapters.emails import Emails
from auth.adapters.sessions import Sessions

@fixture(scope='session')
def settings() -> Settings:
    return Settings()

@fixture(scope='function')
async def database(settings: Settings):
    database = Database(settings)
    await database.setup()
    transaction = await database.connection.begin()
    await database.connection.run_sync(Schema.metadata.create_all)
    try:
        yield database
    finally:
        await transaction.rollback()
        await database.connection.run_sync(Schema.metadata.drop_all)
        await database.teardown()

@fixture(scope='function')
async def cache(settings: Settings):
    cache = Cache(settings)
    await cache.setup()
    try:
        yield cache
    finally:
        await cache.flush()
        await cache.teardown()

@fixture(scope='function')
async def uow(database: Database, cache: Cache):
    async with UnitOfWork(database, cache) as uow:
        yield uow

@fixture(scope='function')
async def users(uow: UnitOfWork):
    return Users(uow)

@fixture(scope='function')
async def accounts(uow: UnitOfWork, users: Users):
    user = await users.create(id=UUID('00000000-0000-0000-0000-000000000000'), name='Test')
    return Accounts(uow, user.pk)

@fixture(scope='function')
async def emails(uow: UnitOfWork, users: Users):
    user = await users.create(id=UUID('00000000-0000-0000-0000-000000000000'), name='Test')
    return Emails(uow, user.pk)

@fixture(scope='function')
async def sessions(uow: UnitOfWork, users: Users):
    user = await users.create(id=UUID('00000000-0000-0000-0000-000000000000'), name='Test')
    return Sessions(uow, user.id)