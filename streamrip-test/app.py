import asyncio
from streamrip.client import QobuzClient
from streamrip.config import Config
# same thing as before
from streamrip.media import Album, PendingAlbum
from streamrip.db import Dummy, Database

config = Config.defaults()
config.session.qobuz.email_or_userid = "david.zehner@outlook.de"
config.session.qobuz.password_or_token = "972d086fd4bb3713522ed0302af6c63c"

client = QobuzClient(config)

db = Database(downloads=Dummy(), failed=Dummy())
p = PendingAlbum("0886443927087", client, config, db)

async def main():
	await client.login()
	print(client.logged_in) # True
	# resolved_album = await p.resolve()
	# print(resolved_album.meta) # print metadata
	# await resolved_album.rip()
	results = await client.search("album", "The Crux Djo", 10)
	print(results)

asyncio.run(main())
