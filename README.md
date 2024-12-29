# FOpS-Bot

Theres lots of stuff here i dont want you to scan or parse at all!

blah blah blah


# Changelog

## Changelog 1

There hasn't been a changelog before this one so tada!

New in version {{version}}
- This cool changelog tracking feature
- Better ways to track issues (on vixi's end)
- Better stability and loading
- Removed some ppl from the holes queue (with plans to make it registerable next update)
- Removed unused services (`ARP_WATCH`, `STAT_GET`)

More to come! I'll have `/register` and `/deregister` working for the holes next update. And hopefully a booru search feature!

## Changelog 2

Ok! Kinda half baked, but news for <@&1248737660315635754>s!

I have added the `/register` and `/deregister` commands, they may be slightly buggy but my early testing says they worked mostly ok! I have some big plans tho and I just wanted to add a quick way right now for people to quickly join and leave when they wish. (dont want anyone being spammed unwillingly).


## Changelog 3

Thank you <@257599292343058433> for reporting this bug.

Fixed in {{version}}
- Deregistering will immediately kick your seat from the queue


## Changelog 4

Hole improvements~

Fixed in {{version}}
- Users registered for the hole cannot be picked twice in a row
- Bot is more helpful when giving errors on registration
- Bot is less spammy
- Booru maintenance bumped to a 10m interval


## Changelog 5

New features!
- instagram supported by the DLP cog! (new cog, just made it~ its epic, you'll see!)
- Facebook also supported~ Will try and do tiktok too but i dont use tiktok so, will have to see how that goes

Fixes in {{version}}
- Fixed the `fluff` text in `/register` (thank you <@257599292343058433>!)


## Changelog 6

Fixes in {{version}}
- DLP cog now supports twitter/x/fixy


## Changelog 7

New command! `/random <tags>` will snatch a random matching post from the booru server~


## Changelog 8

New command `/fav <user=vixi> <tags="">` That will let you get the most recent matching favorite
from your favorite users~

## Changelog 9

Sorry I don't always explain how everything works when I add it~ If you wanna preview more stuff pick
up the <@&1248737660315635754> Role!

Fixes in {{version}}
 - Added better help-text to `/fav` thank you Tyro and Fortune ,3


## Changelog 10

Fixes in {{version}}
 - In-progress commands will no longer be available to users without `Beta Tester` role


## Changelog 11

Added a new command in {{version}}
 - In-progress command `convert_height` will convert your human height into species/anthro height!! YAYY

In the future i deffo tend to add to this function, so lmk any comments~ thanks!


## Changelog 12

BIG NEWS <@&1248737660315635754>s!

So i've been doing a TON of stuff under the hood, mainly.. cleaning up old code XD

I was spending more time chasing bugs than i was actually playing with new features!
Speaking of features.. i now have a much more robust feature system! that actually ties into
the database backend at LAST finally bringing the yaml and dynamic db together!

This means 2 things,

1) I can get back to work on more fun things!
2) The bot can live on *your* servers now! Since configuration is now done on a per-guild basis

PM me for the bot invite!


## Changelog 13

Bot will no longer reply 💎 when auto-upload is not enabled for a channel.

SauceNAO now configured for auto-upload with enhanced confirmation! (feedback welcome)

Fixed a few background task regressions.


## Changelog 14

Removed/unhooked booru functions from the main bot.
