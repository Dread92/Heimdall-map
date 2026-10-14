"""Heimdall — unofficial air-raid / drone tracker for Kyiv and all of Ukraine.

Modules
-------
server     HTTP service, pollers, SQLite store, JSON API and SSE stream
geo        Ukrainian-language parsing: places, headings, counts, official channel formats
translate  offline UA→EN glossary + boilerplate cleaning for the feed
push       Web Push (VAPID / RFC 8291) so the phone rings with the app closed
"""

__version__ = "1.0.0"
