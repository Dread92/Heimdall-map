"""1.58.53 — the jar without its box. The owner: "the jar has some black background which looks bad": on a phone and on a
computer the jar stands on the map by itself, with a soft shadow, and the button keeps its size to hit."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "static", "kyiv.html"), encoding="utf-8") as f:
    PAGE = f.read()


def test_no_box_around_the_jar():
    i = PAGE.index("/* 1.58.53, the owner: \"the jar has some black background")
    blk = PAGE[i:PAGE.index("@media (max-width:999px){.jarbtn .jar3d{width:42px;height:42px}}", i)]
    assert ".jarbtn,body.m-day .jarbtn,body.m-night .jarbtn{background:transparent;border-color:transparent;box-shadow:none;animation:none}" in blk
    assert ".jarbtn .jar3d,.jarbtn svg{filter:drop-shadow(" in blk
    # after every earlier rule that drew a box (1.58.47's gold rim, 1.58.49's phone face), so it wins
    assert i > PAGE.index("/* 1.58.49, the owner (on a phone)") > PAGE.index(".jarbtn{width:54px;height:54px;border:1.5px solid")
    assert ".jarbtn{width:44px;height:44px;padding:0;gap:0;" in PAGE                                  # still 44 px to hit
