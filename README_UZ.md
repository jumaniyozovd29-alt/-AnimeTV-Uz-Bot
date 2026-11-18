# AnimeTV Uz Bot

Telegram bot for looking up anime by numeric code and opening episode video links.

## Railway variables
- `BOT_TOKEN`: token from BotFather (keep secret)
- `ADMIN_ID`: your numeric Telegram user ID
- `DB_PATH`: `/data/anime.db` (default)

Attach a Railway volume at `/data` to preserve the SQLite database across deploys.

## Admin commands
- `/addanime 149 | Anime nomi | Tavsif`
- `/addepisode 149 | 1 | https://example.com/video`
- `/delanime 149`
- `/del episode 149 1`

Users send a numeric anime code and choose an episode. The button opens the supplied external video link.
