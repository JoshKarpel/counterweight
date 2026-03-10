from functools import lru_cache
from typing import Literal

import waxy

from counterweight.styles import BorderKind, CellStyle, Color, Style

Side = Literal["top", "bottom", "left", "right"]

# Start generated

text_white = Style(text_style=CellStyle(foreground=Color.from_hex("#ffffff")))
text_black = Style(text_style=CellStyle(foreground=Color.from_hex("#000000")))

slate_50 = Color.from_hex("#f8fafc")
slate_100 = Color.from_hex("#f1f5f9")
slate_200 = Color.from_hex("#e2e8f0")
slate_300 = Color.from_hex("#cbd5e1")
slate_400 = Color.from_hex("#94a3b8")
slate_500 = Color.from_hex("#64748b")
slate_600 = Color.from_hex("#475569")
slate_700 = Color.from_hex("#334155")
slate_800 = Color.from_hex("#1e293b")
slate_900 = Color.from_hex("#0f172a")
slate_950 = Color.from_hex("#020617")

gray_50 = Color.from_hex("#f9fafb")
gray_100 = Color.from_hex("#f3f4f6")
gray_200 = Color.from_hex("#e5e7eb")
gray_300 = Color.from_hex("#d1d5db")
gray_400 = Color.from_hex("#9ca3af")
gray_500 = Color.from_hex("#6b7280")
gray_600 = Color.from_hex("#4b5563")
gray_700 = Color.from_hex("#374151")
gray_800 = Color.from_hex("#1f2937")
gray_900 = Color.from_hex("#111827")
gray_950 = Color.from_hex("#030712")

zinc_50 = Color.from_hex("#fafafa")
zinc_100 = Color.from_hex("#f4f4f5")
zinc_200 = Color.from_hex("#e4e4e7")
zinc_300 = Color.from_hex("#d4d4d8")
zinc_400 = Color.from_hex("#a1a1aa")
zinc_500 = Color.from_hex("#71717a")
zinc_600 = Color.from_hex("#52525b")
zinc_700 = Color.from_hex("#3f3f46")
zinc_800 = Color.from_hex("#27272a")
zinc_900 = Color.from_hex("#18181b")
zinc_950 = Color.from_hex("#09090b")

neutral_50 = Color.from_hex("#fafafa")
neutral_100 = Color.from_hex("#f5f5f5")
neutral_200 = Color.from_hex("#e5e5e5")
neutral_300 = Color.from_hex("#d4d4d4")
neutral_400 = Color.from_hex("#a3a3a3")
neutral_500 = Color.from_hex("#737373")
neutral_600 = Color.from_hex("#525252")
neutral_700 = Color.from_hex("#404040")
neutral_800 = Color.from_hex("#262626")
neutral_900 = Color.from_hex("#171717")
neutral_950 = Color.from_hex("#0a0a0a")

stone_50 = Color.from_hex("#fafaf9")
stone_100 = Color.from_hex("#f5f5f4")
stone_200 = Color.from_hex("#e7e5e4")
stone_300 = Color.from_hex("#d6d3d1")
stone_400 = Color.from_hex("#a8a29e")
stone_500 = Color.from_hex("#78716c")
stone_600 = Color.from_hex("#57534e")
stone_700 = Color.from_hex("#44403c")
stone_800 = Color.from_hex("#292524")
stone_900 = Color.from_hex("#1c1917")
stone_950 = Color.from_hex("#0c0a09")

red_50 = Color.from_hex("#fef2f2")
red_100 = Color.from_hex("#fee2e2")
red_200 = Color.from_hex("#fecaca")
red_300 = Color.from_hex("#fca5a5")
red_400 = Color.from_hex("#f87171")
red_500 = Color.from_hex("#ef4444")
red_600 = Color.from_hex("#dc2626")
red_700 = Color.from_hex("#b91c1c")
red_800 = Color.from_hex("#991b1b")
red_900 = Color.from_hex("#7f1d1d")
red_950 = Color.from_hex("#450a0a")

orange_50 = Color.from_hex("#fff7ed")
orange_100 = Color.from_hex("#ffedd5")
orange_200 = Color.from_hex("#fed7aa")
orange_300 = Color.from_hex("#fdba74")
orange_400 = Color.from_hex("#fb923c")
orange_500 = Color.from_hex("#f97316")
orange_600 = Color.from_hex("#ea580c")
orange_700 = Color.from_hex("#c2410c")
orange_800 = Color.from_hex("#9a3412")
orange_900 = Color.from_hex("#7c2d12")
orange_950 = Color.from_hex("#431407")

amber_50 = Color.from_hex("#fffbeb")
amber_100 = Color.from_hex("#fef3c7")
amber_200 = Color.from_hex("#fde68a")
amber_300 = Color.from_hex("#fcd34d")
amber_400 = Color.from_hex("#fbbf24")
amber_500 = Color.from_hex("#f59e0b")
amber_600 = Color.from_hex("#d97706")
amber_700 = Color.from_hex("#b45309")
amber_800 = Color.from_hex("#92400e")
amber_900 = Color.from_hex("#78350f")
amber_950 = Color.from_hex("#451a03")

yellow_50 = Color.from_hex("#fefce8")
yellow_100 = Color.from_hex("#fef9c3")
yellow_200 = Color.from_hex("#fef08a")
yellow_300 = Color.from_hex("#fde047")
yellow_400 = Color.from_hex("#facc15")
yellow_500 = Color.from_hex("#eab308")
yellow_600 = Color.from_hex("#ca8a04")
yellow_700 = Color.from_hex("#a16207")
yellow_800 = Color.from_hex("#854d0e")
yellow_900 = Color.from_hex("#713f12")
yellow_950 = Color.from_hex("#422006")

lime_50 = Color.from_hex("#f7fee7")
lime_100 = Color.from_hex("#ecfccb")
lime_200 = Color.from_hex("#d9f99d")
lime_300 = Color.from_hex("#bef264")
lime_400 = Color.from_hex("#a3e635")
lime_500 = Color.from_hex("#84cc16")
lime_600 = Color.from_hex("#65a30d")
lime_700 = Color.from_hex("#4d7c0f")
lime_800 = Color.from_hex("#3f6212")
lime_900 = Color.from_hex("#365314")
lime_950 = Color.from_hex("#1a2e05")

green_50 = Color.from_hex("#f0fdf4")
green_100 = Color.from_hex("#dcfce7")
green_200 = Color.from_hex("#bbf7d0")
green_300 = Color.from_hex("#86efac")
green_400 = Color.from_hex("#4ade80")
green_500 = Color.from_hex("#22c55e")
green_600 = Color.from_hex("#16a34a")
green_700 = Color.from_hex("#15803d")
green_800 = Color.from_hex("#166534")
green_900 = Color.from_hex("#14532d")
green_950 = Color.from_hex("#052e16")

emerald_50 = Color.from_hex("#ecfdf5")
emerald_100 = Color.from_hex("#d1fae5")
emerald_200 = Color.from_hex("#a7f3d0")
emerald_300 = Color.from_hex("#6ee7b7")
emerald_400 = Color.from_hex("#34d399")
emerald_500 = Color.from_hex("#10b981")
emerald_600 = Color.from_hex("#059669")
emerald_700 = Color.from_hex("#047857")
emerald_800 = Color.from_hex("#065f46")
emerald_900 = Color.from_hex("#064e3b")
emerald_950 = Color.from_hex("#022c22")

teal_50 = Color.from_hex("#f0fdfa")
teal_100 = Color.from_hex("#ccfbf1")
teal_200 = Color.from_hex("#99f6e4")
teal_300 = Color.from_hex("#5eead4")
teal_400 = Color.from_hex("#2dd4bf")
teal_500 = Color.from_hex("#14b8a6")
teal_600 = Color.from_hex("#0d9488")
teal_700 = Color.from_hex("#0f766e")
teal_800 = Color.from_hex("#115e59")
teal_900 = Color.from_hex("#134e4a")
teal_950 = Color.from_hex("#042f2e")

cyan_50 = Color.from_hex("#ecfeff")
cyan_100 = Color.from_hex("#cffafe")
cyan_200 = Color.from_hex("#a5f3fc")
cyan_300 = Color.from_hex("#67e8f9")
cyan_400 = Color.from_hex("#22d3ee")
cyan_500 = Color.from_hex("#06b6d4")
cyan_600 = Color.from_hex("#0891b2")
cyan_700 = Color.from_hex("#0e7490")
cyan_800 = Color.from_hex("#155e75")
cyan_900 = Color.from_hex("#164e63")
cyan_950 = Color.from_hex("#083344")

sky_50 = Color.from_hex("#f0f9ff")
sky_100 = Color.from_hex("#e0f2fe")
sky_200 = Color.from_hex("#bae6fd")
sky_300 = Color.from_hex("#7dd3fc")
sky_400 = Color.from_hex("#38bdf8")
sky_500 = Color.from_hex("#0ea5e9")
sky_600 = Color.from_hex("#0284c7")
sky_700 = Color.from_hex("#0369a1")
sky_800 = Color.from_hex("#075985")
sky_900 = Color.from_hex("#0c4a6e")
sky_950 = Color.from_hex("#082f49")

blue_50 = Color.from_hex("#eff6ff")
blue_100 = Color.from_hex("#dbeafe")
blue_200 = Color.from_hex("#bfdbfe")
blue_300 = Color.from_hex("#93c5fd")
blue_400 = Color.from_hex("#60a5fa")
blue_500 = Color.from_hex("#3b82f6")
blue_600 = Color.from_hex("#2563eb")
blue_700 = Color.from_hex("#1d4ed8")
blue_800 = Color.from_hex("#1e40af")
blue_900 = Color.from_hex("#1e3a8a")
blue_950 = Color.from_hex("#172554")

indigo_50 = Color.from_hex("#eef2ff")
indigo_100 = Color.from_hex("#e0e7ff")
indigo_200 = Color.from_hex("#c7d2fe")
indigo_300 = Color.from_hex("#a5b4fc")
indigo_400 = Color.from_hex("#818cf8")
indigo_500 = Color.from_hex("#6366f1")
indigo_600 = Color.from_hex("#4f46e5")
indigo_700 = Color.from_hex("#4338ca")
indigo_800 = Color.from_hex("#3730a3")
indigo_900 = Color.from_hex("#312e81")
indigo_950 = Color.from_hex("#1e1b4b")

violet_50 = Color.from_hex("#f5f3ff")
violet_100 = Color.from_hex("#ede9fe")
violet_200 = Color.from_hex("#ddd6fe")
violet_300 = Color.from_hex("#c4b5fd")
violet_400 = Color.from_hex("#a78bfa")
violet_500 = Color.from_hex("#8b5cf6")
violet_600 = Color.from_hex("#7c3aed")
violet_700 = Color.from_hex("#6d28d9")
violet_800 = Color.from_hex("#5b21b6")
violet_900 = Color.from_hex("#4c1d95")
violet_950 = Color.from_hex("#2e1065")

purple_50 = Color.from_hex("#faf5ff")
purple_100 = Color.from_hex("#f3e8ff")
purple_200 = Color.from_hex("#e9d5ff")
purple_300 = Color.from_hex("#d8b4fe")
purple_400 = Color.from_hex("#c084fc")
purple_500 = Color.from_hex("#a855f7")
purple_600 = Color.from_hex("#9333ea")
purple_700 = Color.from_hex("#7e22ce")
purple_800 = Color.from_hex("#6b21a8")
purple_900 = Color.from_hex("#581c87")
purple_950 = Color.from_hex("#3b0764")

fuchsia_50 = Color.from_hex("#fdf4ff")
fuchsia_100 = Color.from_hex("#fae8ff")
fuchsia_200 = Color.from_hex("#f5d0fe")
fuchsia_300 = Color.from_hex("#f0abfc")
fuchsia_400 = Color.from_hex("#e879f9")
fuchsia_500 = Color.from_hex("#d946ef")
fuchsia_600 = Color.from_hex("#c026d3")
fuchsia_700 = Color.from_hex("#a21caf")
fuchsia_800 = Color.from_hex("#86198f")
fuchsia_900 = Color.from_hex("#701a75")
fuchsia_950 = Color.from_hex("#4a044e")

pink_50 = Color.from_hex("#fdf2f8")
pink_100 = Color.from_hex("#fce7f3")
pink_200 = Color.from_hex("#fbcfe8")
pink_300 = Color.from_hex("#f9a8d4")
pink_400 = Color.from_hex("#f472b6")
pink_500 = Color.from_hex("#ec4899")
pink_600 = Color.from_hex("#db2777")
pink_700 = Color.from_hex("#be185d")
pink_800 = Color.from_hex("#9d174d")
pink_900 = Color.from_hex("#831843")
pink_950 = Color.from_hex("#500724")

rose_50 = Color.from_hex("#fff1f2")
rose_100 = Color.from_hex("#ffe4e6")
rose_200 = Color.from_hex("#fecdd3")
rose_300 = Color.from_hex("#fda4af")
rose_400 = Color.from_hex("#fb7185")
rose_500 = Color.from_hex("#f43f5e")
rose_600 = Color.from_hex("#e11d48")
rose_700 = Color.from_hex("#be123c")
rose_800 = Color.from_hex("#9f1239")
rose_900 = Color.from_hex("#881337")
rose_950 = Color.from_hex("#4c0519")

ColorName = Literal[
    "slate",
    "gray",
    "zinc",
    "neutral",
    "stone",
    "red",
    "orange",
    "amber",
    "yellow",
    "lime",
    "green",
    "emerald",
    "teal",
    "cyan",
    "sky",
    "blue",
    "indigo",
    "violet",
    "purple",
    "fuchsia",
    "pink",
    "rose",
]
Shade = Literal[50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]

_COLOR_MAP: dict[tuple[str, int], Color] = {
    ("slate", 50): slate_50,
    ("slate", 100): slate_100,
    ("slate", 200): slate_200,
    ("slate", 300): slate_300,
    ("slate", 400): slate_400,
    ("slate", 500): slate_500,
    ("slate", 600): slate_600,
    ("slate", 700): slate_700,
    ("slate", 800): slate_800,
    ("slate", 900): slate_900,
    ("slate", 950): slate_950,
    ("gray", 50): gray_50,
    ("gray", 100): gray_100,
    ("gray", 200): gray_200,
    ("gray", 300): gray_300,
    ("gray", 400): gray_400,
    ("gray", 500): gray_500,
    ("gray", 600): gray_600,
    ("gray", 700): gray_700,
    ("gray", 800): gray_800,
    ("gray", 900): gray_900,
    ("gray", 950): gray_950,
    ("zinc", 50): zinc_50,
    ("zinc", 100): zinc_100,
    ("zinc", 200): zinc_200,
    ("zinc", 300): zinc_300,
    ("zinc", 400): zinc_400,
    ("zinc", 500): zinc_500,
    ("zinc", 600): zinc_600,
    ("zinc", 700): zinc_700,
    ("zinc", 800): zinc_800,
    ("zinc", 900): zinc_900,
    ("zinc", 950): zinc_950,
    ("neutral", 50): neutral_50,
    ("neutral", 100): neutral_100,
    ("neutral", 200): neutral_200,
    ("neutral", 300): neutral_300,
    ("neutral", 400): neutral_400,
    ("neutral", 500): neutral_500,
    ("neutral", 600): neutral_600,
    ("neutral", 700): neutral_700,
    ("neutral", 800): neutral_800,
    ("neutral", 900): neutral_900,
    ("neutral", 950): neutral_950,
    ("stone", 50): stone_50,
    ("stone", 100): stone_100,
    ("stone", 200): stone_200,
    ("stone", 300): stone_300,
    ("stone", 400): stone_400,
    ("stone", 500): stone_500,
    ("stone", 600): stone_600,
    ("stone", 700): stone_700,
    ("stone", 800): stone_800,
    ("stone", 900): stone_900,
    ("stone", 950): stone_950,
    ("red", 50): red_50,
    ("red", 100): red_100,
    ("red", 200): red_200,
    ("red", 300): red_300,
    ("red", 400): red_400,
    ("red", 500): red_500,
    ("red", 600): red_600,
    ("red", 700): red_700,
    ("red", 800): red_800,
    ("red", 900): red_900,
    ("red", 950): red_950,
    ("orange", 50): orange_50,
    ("orange", 100): orange_100,
    ("orange", 200): orange_200,
    ("orange", 300): orange_300,
    ("orange", 400): orange_400,
    ("orange", 500): orange_500,
    ("orange", 600): orange_600,
    ("orange", 700): orange_700,
    ("orange", 800): orange_800,
    ("orange", 900): orange_900,
    ("orange", 950): orange_950,
    ("amber", 50): amber_50,
    ("amber", 100): amber_100,
    ("amber", 200): amber_200,
    ("amber", 300): amber_300,
    ("amber", 400): amber_400,
    ("amber", 500): amber_500,
    ("amber", 600): amber_600,
    ("amber", 700): amber_700,
    ("amber", 800): amber_800,
    ("amber", 900): amber_900,
    ("amber", 950): amber_950,
    ("yellow", 50): yellow_50,
    ("yellow", 100): yellow_100,
    ("yellow", 200): yellow_200,
    ("yellow", 300): yellow_300,
    ("yellow", 400): yellow_400,
    ("yellow", 500): yellow_500,
    ("yellow", 600): yellow_600,
    ("yellow", 700): yellow_700,
    ("yellow", 800): yellow_800,
    ("yellow", 900): yellow_900,
    ("yellow", 950): yellow_950,
    ("lime", 50): lime_50,
    ("lime", 100): lime_100,
    ("lime", 200): lime_200,
    ("lime", 300): lime_300,
    ("lime", 400): lime_400,
    ("lime", 500): lime_500,
    ("lime", 600): lime_600,
    ("lime", 700): lime_700,
    ("lime", 800): lime_800,
    ("lime", 900): lime_900,
    ("lime", 950): lime_950,
    ("green", 50): green_50,
    ("green", 100): green_100,
    ("green", 200): green_200,
    ("green", 300): green_300,
    ("green", 400): green_400,
    ("green", 500): green_500,
    ("green", 600): green_600,
    ("green", 700): green_700,
    ("green", 800): green_800,
    ("green", 900): green_900,
    ("green", 950): green_950,
    ("emerald", 50): emerald_50,
    ("emerald", 100): emerald_100,
    ("emerald", 200): emerald_200,
    ("emerald", 300): emerald_300,
    ("emerald", 400): emerald_400,
    ("emerald", 500): emerald_500,
    ("emerald", 600): emerald_600,
    ("emerald", 700): emerald_700,
    ("emerald", 800): emerald_800,
    ("emerald", 900): emerald_900,
    ("emerald", 950): emerald_950,
    ("teal", 50): teal_50,
    ("teal", 100): teal_100,
    ("teal", 200): teal_200,
    ("teal", 300): teal_300,
    ("teal", 400): teal_400,
    ("teal", 500): teal_500,
    ("teal", 600): teal_600,
    ("teal", 700): teal_700,
    ("teal", 800): teal_800,
    ("teal", 900): teal_900,
    ("teal", 950): teal_950,
    ("cyan", 50): cyan_50,
    ("cyan", 100): cyan_100,
    ("cyan", 200): cyan_200,
    ("cyan", 300): cyan_300,
    ("cyan", 400): cyan_400,
    ("cyan", 500): cyan_500,
    ("cyan", 600): cyan_600,
    ("cyan", 700): cyan_700,
    ("cyan", 800): cyan_800,
    ("cyan", 900): cyan_900,
    ("cyan", 950): cyan_950,
    ("sky", 50): sky_50,
    ("sky", 100): sky_100,
    ("sky", 200): sky_200,
    ("sky", 300): sky_300,
    ("sky", 400): sky_400,
    ("sky", 500): sky_500,
    ("sky", 600): sky_600,
    ("sky", 700): sky_700,
    ("sky", 800): sky_800,
    ("sky", 900): sky_900,
    ("sky", 950): sky_950,
    ("blue", 50): blue_50,
    ("blue", 100): blue_100,
    ("blue", 200): blue_200,
    ("blue", 300): blue_300,
    ("blue", 400): blue_400,
    ("blue", 500): blue_500,
    ("blue", 600): blue_600,
    ("blue", 700): blue_700,
    ("blue", 800): blue_800,
    ("blue", 900): blue_900,
    ("blue", 950): blue_950,
    ("indigo", 50): indigo_50,
    ("indigo", 100): indigo_100,
    ("indigo", 200): indigo_200,
    ("indigo", 300): indigo_300,
    ("indigo", 400): indigo_400,
    ("indigo", 500): indigo_500,
    ("indigo", 600): indigo_600,
    ("indigo", 700): indigo_700,
    ("indigo", 800): indigo_800,
    ("indigo", 900): indigo_900,
    ("indigo", 950): indigo_950,
    ("violet", 50): violet_50,
    ("violet", 100): violet_100,
    ("violet", 200): violet_200,
    ("violet", 300): violet_300,
    ("violet", 400): violet_400,
    ("violet", 500): violet_500,
    ("violet", 600): violet_600,
    ("violet", 700): violet_700,
    ("violet", 800): violet_800,
    ("violet", 900): violet_900,
    ("violet", 950): violet_950,
    ("purple", 50): purple_50,
    ("purple", 100): purple_100,
    ("purple", 200): purple_200,
    ("purple", 300): purple_300,
    ("purple", 400): purple_400,
    ("purple", 500): purple_500,
    ("purple", 600): purple_600,
    ("purple", 700): purple_700,
    ("purple", 800): purple_800,
    ("purple", 900): purple_900,
    ("purple", 950): purple_950,
    ("fuchsia", 50): fuchsia_50,
    ("fuchsia", 100): fuchsia_100,
    ("fuchsia", 200): fuchsia_200,
    ("fuchsia", 300): fuchsia_300,
    ("fuchsia", 400): fuchsia_400,
    ("fuchsia", 500): fuchsia_500,
    ("fuchsia", 600): fuchsia_600,
    ("fuchsia", 700): fuchsia_700,
    ("fuchsia", 800): fuchsia_800,
    ("fuchsia", 900): fuchsia_900,
    ("fuchsia", 950): fuchsia_950,
    ("pink", 50): pink_50,
    ("pink", 100): pink_100,
    ("pink", 200): pink_200,
    ("pink", 300): pink_300,
    ("pink", 400): pink_400,
    ("pink", 500): pink_500,
    ("pink", 600): pink_600,
    ("pink", 700): pink_700,
    ("pink", 800): pink_800,
    ("pink", 900): pink_900,
    ("pink", 950): pink_950,
    ("rose", 50): rose_50,
    ("rose", 100): rose_100,
    ("rose", 200): rose_200,
    ("rose", 300): rose_300,
    ("rose", 400): rose_400,
    ("rose", 500): rose_500,
    ("rose", 600): rose_600,
    ("rose", 700): rose_700,
    ("rose", 800): rose_800,
    ("rose", 900): rose_900,
    ("rose", 950): rose_950,
}

row = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Row))
col = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Column))
row_reverse = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.RowReverse))
col_reverse = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.ColumnReverse))

justify_children_start = Style(layout=waxy.Style(justify_content=waxy.AlignContent.Start))
justify_children_center = Style(layout=waxy.Style(justify_content=waxy.AlignContent.Center))
justify_children_end = Style(layout=waxy.Style(justify_content=waxy.AlignContent.End))
justify_children_space_between = Style(layout=waxy.Style(justify_content=waxy.AlignContent.SpaceBetween))
justify_children_space_around = Style(layout=waxy.Style(justify_content=waxy.AlignContent.SpaceAround))
justify_children_space_evenly = Style(layout=waxy.Style(justify_content=waxy.AlignContent.SpaceEvenly))

align_children_start = Style(layout=waxy.Style(align_items=waxy.AlignItems.Start))
align_children_center = Style(layout=waxy.Style(align_items=waxy.AlignItems.Center))
align_children_end = Style(layout=waxy.Style(align_items=waxy.AlignItems.End))
align_children_stretch = Style(layout=waxy.Style(align_items=waxy.AlignItems.Stretch))

align_self_start = Style(layout=waxy.Style(align_self=waxy.AlignItems.Start))
align_self_center = Style(layout=waxy.Style(align_self=waxy.AlignItems.Center))
align_self_end = Style(layout=waxy.Style(align_self=waxy.AlignItems.End))
align_self_stretch = Style(layout=waxy.Style(align_self=waxy.AlignItems.Stretch))

justify_items_start = Style(layout=waxy.Style(justify_items=waxy.AlignItems.Start))
justify_items_center = Style(layout=waxy.Style(justify_items=waxy.AlignItems.Center))
justify_items_end = Style(layout=waxy.Style(justify_items=waxy.AlignItems.End))
justify_items_stretch = Style(layout=waxy.Style(justify_items=waxy.AlignItems.Stretch))

justify_self_start = Style(layout=waxy.Style(justify_self=waxy.AlignItems.Start))
justify_self_center = Style(layout=waxy.Style(justify_self=waxy.AlignItems.Center))
justify_self_end = Style(layout=waxy.Style(justify_self=waxy.AlignItems.End))
justify_self_stretch = Style(layout=waxy.Style(justify_self=waxy.AlignItems.Stretch))


flex_no_wrap = Style(layout=waxy.Style(flex_wrap=waxy.FlexWrap.NoWrap))
flex_wrap = Style(layout=waxy.Style(flex_wrap=waxy.FlexWrap.Wrap))
flex_wrap_reverse = Style(layout=waxy.Style(flex_wrap=waxy.FlexWrap.WrapReverse))

display_flex = Style(layout=waxy.Style(display=waxy.Display.Flex))
display_block = Style(layout=waxy.Style(display=waxy.Display.Block))
display_grid = Style(layout=waxy.Style(display=waxy.Display.Grid))
display_none = Style(layout=waxy.Style(display=waxy.Display.Nil))

grid_auto_flow_row = Style(layout=waxy.Style(grid_auto_flow=waxy.GridAutoFlow.Row))
grid_auto_flow_column = Style(layout=waxy.Style(grid_auto_flow=waxy.GridAutoFlow.Column))
grid_auto_flow_row_dense = Style(layout=waxy.Style(grid_auto_flow=waxy.GridAutoFlow.RowDense))
grid_auto_flow_column_dense = Style(layout=waxy.Style(grid_auto_flow=waxy.GridAutoFlow.ColumnDense))

border_none = Style(border_kind=None)
border_light = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1),
        border_bottom=waxy.Length(1),
        border_left=waxy.Length(1),
        border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.Light,
)
border_lightrounded = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1),
        border_bottom=waxy.Length(1),
        border_left=waxy.Length(1),
        border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.LightRounded,
)
border_lightangled = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1),
        border_bottom=waxy.Length(1),
        border_left=waxy.Length(1),
        border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.LightAngled,
)
border_heavy = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1),
        border_bottom=waxy.Length(1),
        border_left=waxy.Length(1),
        border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.Heavy,
)
border_double = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1),
        border_bottom=waxy.Length(1),
        border_left=waxy.Length(1),
        border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.Double,
)
border_thick = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1),
        border_bottom=waxy.Length(1),
        border_left=waxy.Length(1),
        border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.Thick,
)
border_mcgugan = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1),
        border_bottom=waxy.Length(1),
        border_left=waxy.Length(1),
        border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.McGugan,
)
border_lightshade = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1),
        border_bottom=waxy.Length(1),
        border_left=waxy.Length(1),
        border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.LightShade,
)
border_mediumshade = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1),
        border_bottom=waxy.Length(1),
        border_left=waxy.Length(1),
        border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.MediumShade,
)
border_heavyshade = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1),
        border_bottom=waxy.Length(1),
        border_left=waxy.Length(1),
        border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.HeavyShade,
)
border_star = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1),
        border_bottom=waxy.Length(1),
        border_left=waxy.Length(1),
        border_right=waxy.Length(1),
    ),
    border_kind=BorderKind.Star,
)

border_top = Style(layout=waxy.Style(border_top=waxy.Length(1)))
border_bottom = Style(layout=waxy.Style(border_bottom=waxy.Length(1)))
border_left = Style(layout=waxy.Style(border_left=waxy.Length(1)))
border_right = Style(layout=waxy.Style(border_right=waxy.Length(1)))
border_top_bottom = Style(layout=waxy.Style(border_top=waxy.Length(1), border_bottom=waxy.Length(1)))
border_top_left = Style(layout=waxy.Style(border_top=waxy.Length(1), border_left=waxy.Length(1)))
border_top_right = Style(layout=waxy.Style(border_top=waxy.Length(1), border_right=waxy.Length(1)))
border_bottom_left = Style(layout=waxy.Style(border_bottom=waxy.Length(1), border_left=waxy.Length(1)))
border_bottom_right = Style(layout=waxy.Style(border_bottom=waxy.Length(1), border_right=waxy.Length(1)))
border_left_right = Style(layout=waxy.Style(border_left=waxy.Length(1), border_right=waxy.Length(1)))
border_top_bottom_left = Style(
    layout=waxy.Style(border_top=waxy.Length(1), border_bottom=waxy.Length(1), border_left=waxy.Length(1))
)
border_top_bottom_right = Style(
    layout=waxy.Style(border_top=waxy.Length(1), border_bottom=waxy.Length(1), border_right=waxy.Length(1))
)
border_top_left_right = Style(
    layout=waxy.Style(border_top=waxy.Length(1), border_left=waxy.Length(1), border_right=waxy.Length(1))
)
border_bottom_left_right = Style(
    layout=waxy.Style(border_bottom=waxy.Length(1), border_left=waxy.Length(1), border_right=waxy.Length(1))
)
border_all = Style(
    layout=waxy.Style(
        border_top=waxy.Length(1), border_bottom=waxy.Length(1), border_left=waxy.Length(1), border_right=waxy.Length(1)
    )
)

inset_top_left = Style(
    layout=waxy.Style(position=waxy.Position.Absolute, inset_top=waxy.Length(0), inset_left=waxy.Length(0))
)
inset_top_center = Style(
    layout=waxy.Style(
        position=waxy.Position.Absolute, inset_top=waxy.Length(0), inset_left=waxy.Auto(), inset_right=waxy.Auto()
    )
)
inset_top_right = Style(
    layout=waxy.Style(position=waxy.Position.Absolute, inset_top=waxy.Length(0), inset_right=waxy.Length(0))
)
inset_center_left = Style(
    layout=waxy.Style(
        position=waxy.Position.Absolute, inset_top=waxy.Auto(), inset_bottom=waxy.Auto(), inset_left=waxy.Length(0)
    )
)
inset_center_center = Style(
    layout=waxy.Style(
        position=waxy.Position.Absolute,
        inset_top=waxy.Auto(),
        inset_bottom=waxy.Auto(),
        inset_left=waxy.Auto(),
        inset_right=waxy.Auto(),
    )
)
inset_center_right = Style(
    layout=waxy.Style(
        position=waxy.Position.Absolute, inset_top=waxy.Auto(), inset_bottom=waxy.Auto(), inset_right=waxy.Length(0)
    )
)
inset_bottom_left = Style(
    layout=waxy.Style(position=waxy.Position.Absolute, inset_bottom=waxy.Length(0), inset_left=waxy.Length(0))
)
inset_bottom_center = Style(
    layout=waxy.Style(
        position=waxy.Position.Absolute, inset_bottom=waxy.Length(0), inset_left=waxy.Auto(), inset_right=waxy.Auto()
    )
)
inset_bottom_right = Style(
    layout=waxy.Style(position=waxy.Position.Absolute, inset_bottom=waxy.Length(0), inset_right=waxy.Length(0))
)

text_justify_left = Style(text_justify="left")
text_justify_center = Style(text_justify="center")
text_justify_right = Style(text_justify="right")

text_wrap_none = Style(text_wrap="none")
text_wrap_stable = Style(text_wrap="stable")
text_wrap_balance = Style(text_wrap="balance")
text_wrap_pretty = Style(text_wrap="pretty")

# Stop generated


default = Style()

position_relative = Style(layout=waxy.Style(position=waxy.Position.Relative))
position_absolute = Style(layout=waxy.Style(position=waxy.Position.Absolute))

border_collapse = Style(layout=waxy.Style(gap_width=waxy.Length(-1), gap_height=waxy.Length(-1)))

content_box = Style(layout=waxy.Style(box_sizing=waxy.BoxSizing.ContentBox))
border_box = Style(layout=waxy.Style(box_sizing=waxy.BoxSizing.BorderBox))


@lru_cache(maxsize=256)
def grow(n: float) -> Style:
    return Style(layout=waxy.Style(flex_grow=float(n), flex_basis=waxy.Length(0)))


@lru_cache(maxsize=256)
def shrink(n: float) -> Style:
    return Style(layout=waxy.Style(flex_shrink=float(n)))


full_width = Style(layout=waxy.Style(size_width=waxy.Percent(1.0)))
full_height = Style(layout=waxy.Style(size_height=waxy.Percent(1.0)))
full = Style(layout=waxy.Style(size_width=waxy.Percent(1.0), size_height=waxy.Percent(1.0)))


@lru_cache(maxsize=256)
def inset_top(n: int) -> Style:
    return Style(layout=waxy.Style(inset_top=waxy.Length(n)))


@lru_cache(maxsize=256)
def inset_bottom(n: int) -> Style:
    return Style(layout=waxy.Style(inset_bottom=waxy.Length(n)))


@lru_cache(maxsize=256)
def inset_left(n: int) -> Style:
    return Style(layout=waxy.Style(inset_left=waxy.Length(n)))


@lru_cache(maxsize=256)
def inset_right(n: int) -> Style:
    return Style(layout=waxy.Style(inset_right=waxy.Length(n)))


@lru_cache(maxsize=256)
def z(z: int = 0) -> Style:
    return Style(z=z)


@lru_cache(maxsize=256)
def width(n: int) -> Style:
    return Style(layout=waxy.Style(size_width=waxy.Length(n)))


@lru_cache(maxsize=256)
def height(n: int) -> Style:
    return Style(layout=waxy.Style(size_height=waxy.Length(n)))


@lru_cache(maxsize=256)
def size(w: int, h: int) -> Style:
    return Style(layout=waxy.Style(size_width=waxy.Length(w), size_height=waxy.Length(h)))


@lru_cache(maxsize=256)
def min_width(n: int) -> Style:
    return Style(layout=waxy.Style(min_size_width=waxy.Length(n)))


@lru_cache(maxsize=256)
def min_height(n: int) -> Style:
    return Style(layout=waxy.Style(min_size_height=waxy.Length(n)))


@lru_cache(maxsize=256)
def max_width(n: int) -> Style:
    return Style(layout=waxy.Style(max_size_width=waxy.Length(n)))


@lru_cache(maxsize=256)
def max_height(n: int) -> Style:
    return Style(layout=waxy.Style(max_size_height=waxy.Length(n)))


@lru_cache(maxsize=256)
def aspect_ratio(ratio: float) -> Style:
    return Style(layout=waxy.Style(aspect_ratio=ratio))


@lru_cache(maxsize=256)
def grid_template_rows(*tracks: waxy.GridTrackValue) -> Style:
    return Style(layout=waxy.Style(grid_template_rows=list(tracks)))


@lru_cache(maxsize=256)
def grid_template_columns(*tracks: waxy.GridTrackValue) -> Style:
    return Style(layout=waxy.Style(grid_template_columns=list(tracks)))


@lru_cache(maxsize=256)
def grid_row(start: waxy.GridPlacementValue | None = None, end: waxy.GridPlacementValue | None = None) -> Style:
    return Style(layout=waxy.Style(grid_row=waxy.GridPlacement(start=start, end=end)))


@lru_cache(maxsize=256)
def grid_column(start: waxy.GridPlacementValue | None = None, end: waxy.GridPlacementValue | None = None) -> Style:
    return Style(layout=waxy.Style(grid_column=waxy.GridPlacement(start=start, end=end)))


@lru_cache(maxsize=256)
def border_contract(n: int) -> Style:
    return Style(border_contract=n)


@lru_cache(maxsize=256)
def border_sides(sides: frozenset[Side]) -> Style:
    return Style(
        layout=waxy.Style(
            border_top=waxy.Length(1 if "top" in sides else 0),
            border_bottom=waxy.Length(1 if "bottom" in sides else 0),
            border_left=waxy.Length(1 if "left" in sides else 0),
            border_right=waxy.Length(1 if "right" in sides else 0),
        )
    )


@lru_cache(maxsize=256)
def margin_top(n: int) -> Style:
    return Style(layout=waxy.Style(margin_top=waxy.Length(n)))


@lru_cache(maxsize=256)
def margin_bottom(n: int) -> Style:
    return Style(layout=waxy.Style(margin_bottom=waxy.Length(n)))


@lru_cache(maxsize=256)
def margin_left(n: int) -> Style:
    return Style(layout=waxy.Style(margin_left=waxy.Length(n)))


@lru_cache(maxsize=256)
def margin_right(n: int) -> Style:
    return Style(layout=waxy.Style(margin_right=waxy.Length(n)))


@lru_cache(maxsize=256)
def margin_x(n: int) -> Style:
    return Style(layout=waxy.Style(margin_left=waxy.Length(n), margin_right=waxy.Length(n)))


@lru_cache(maxsize=256)
def margin_y(n: int) -> Style:
    return Style(layout=waxy.Style(margin_top=waxy.Length(n), margin_bottom=waxy.Length(n)))


@lru_cache(maxsize=256)
def margin(n: int) -> Style:
    return Style(
        layout=waxy.Style(
            margin_top=waxy.Length(n),
            margin_bottom=waxy.Length(n),
            margin_left=waxy.Length(n),
            margin_right=waxy.Length(n),
        )
    )


@lru_cache(maxsize=256)
def gap_width(n: int) -> Style:
    return Style(layout=waxy.Style(gap_width=waxy.Length(n)))


@lru_cache(maxsize=256)
def gap_height(n: int) -> Style:
    return Style(layout=waxy.Style(gap_height=waxy.Length(n)))


@lru_cache(maxsize=256)
def gap(n: int) -> Style:
    return Style(layout=waxy.Style(gap_width=waxy.Length(n), gap_height=waxy.Length(n)))


@lru_cache(maxsize=256)
def pad(n: int) -> Style:
    return Style(
        layout=waxy.Style(
            padding_top=waxy.Length(n),
            padding_bottom=waxy.Length(n),
            padding_left=waxy.Length(n),
            padding_right=waxy.Length(n),
        )
    )


@lru_cache(maxsize=256)
def pad_x(n: int) -> Style:
    return Style(layout=waxy.Style(padding_left=waxy.Length(n), padding_right=waxy.Length(n)))


@lru_cache(maxsize=256)
def pad_y(n: int) -> Style:
    return Style(layout=waxy.Style(padding_top=waxy.Length(n), padding_bottom=waxy.Length(n)))


@lru_cache(maxsize=256)
def pad_top(n: int) -> Style:
    return Style(layout=waxy.Style(padding_top=waxy.Length(n)))


@lru_cache(maxsize=256)
def pad_bottom(n: int) -> Style:
    return Style(layout=waxy.Style(padding_bottom=waxy.Length(n)))


@lru_cache(maxsize=256)
def pad_left(n: int) -> Style:
    return Style(layout=waxy.Style(padding_left=waxy.Length(n)))


@lru_cache(maxsize=256)
def pad_right(n: int) -> Style:
    return Style(layout=waxy.Style(padding_right=waxy.Length(n)))


@lru_cache(maxsize=256)
def text_color(color: ColorName, shade: Shade) -> Style:
    return Style(text_style=CellStyle(foreground=_COLOR_MAP[(color, shade)]))


@lru_cache(maxsize=256)
def text_bg(color: ColorName, shade: Shade) -> Style:
    return Style(text_style=CellStyle(background=_COLOR_MAP[(color, shade)]))


@lru_cache(maxsize=256)
def border_color(color: ColorName, shade: Shade) -> Style:
    return Style(border_style=CellStyle(foreground=_COLOR_MAP[(color, shade)]))


@lru_cache(maxsize=256)
def border_bg(color: ColorName, shade: Shade) -> Style:
    return Style(border_style=CellStyle(background=_COLOR_MAP[(color, shade)]))


@lru_cache(maxsize=256)
def margin_color(color: ColorName, shade: Shade) -> Style:
    return Style(margin_color=_COLOR_MAP[(color, shade)])


@lru_cache(maxsize=256)
def padding_color(color: ColorName, shade: Shade) -> Style:
    return Style(padding_color=_COLOR_MAP[(color, shade)])


@lru_cache(maxsize=256)
def content_color(color: ColorName, shade: Shade) -> Style:
    return Style(content_color=_COLOR_MAP[(color, shade)])
