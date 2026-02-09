"""
Seed data for the Song Factory app.
Contains genres, lore entries, and pre-written songs for the Yakima Finds universe.
"""

# ---------------------------------------------------------------------------
# 1. SEED_GENRES
# ---------------------------------------------------------------------------

SEED_GENRES = [
    {
        "name": "Pop",
        "prompt_template": "Upbeat synth-pop, bright vocals, catchy chorus, shimmering synths, handclaps, feel-good summer energy, radio-ready",
        "description": "Bright, catchy pop with shimmering synths and feel-good energy.",
        "bpm_range": "110-130",
        "active": True,
    },
    {
        "name": "Hip-Hop",
        "prompt_template": "Hard trap beat, melodic hook, 808 bass, hi-hats, confident male rap, bouncy rhythm, modern hip-hop",
        "description": "Modern hip-hop with trap beats, 808 bass, and confident vocals.",
        "bpm_range": "130-145",
        "active": True,
    },
    {
        "name": "Rock",
        "prompt_template": "Driving arena rock, electric guitars, powerful drums, big chorus gang vocals, gritty male lead",
        "description": "Driving arena rock with electric guitars and powerful drums.",
        "bpm_range": "120-140",
        "active": True,
    },
    {
        "name": "Country",
        "prompt_template": "Modern country pop, acoustic guitar, warm male vocals, storytelling, singalong chorus, slide guitar, fiddle",
        "description": "Modern country pop with acoustic guitar, warm vocals, and storytelling.",
        "bpm_range": "100-115",
        "active": True,
    },
    {
        "name": "Latin / Reggaeton",
        "prompt_template": "Reggaeton dembow beat, bilingual hook, tropical synths, Latin pop energy, male vocals, urban Latin",
        "description": "Reggaeton with dembow beats, tropical synths, and Latin pop energy.",
        "bpm_range": "90-100",
        "active": True,
    },
    {
        "name": "EDM / Dance",
        "prompt_template": "High energy EDM anthem, big synth build and drop, female vocal chops, four-on-the-floor, future rave",
        "description": "High-energy EDM anthems with big drops and four-on-the-floor beats.",
        "bpm_range": "125-132",
        "active": True,
    },
    {
        "name": "R&B / Soul",
        "prompt_template": "Smooth neo-soul, Rhodes piano, mellow bass, silky female vocals, lush harmonies, vintage soul meets modern R&B",
        "description": "Smooth neo-soul with Rhodes piano, lush harmonies, and silky vocals.",
        "bpm_range": "85-95",
        "active": True,
    },
    {
        "name": "Indie Pop",
        "prompt_template": "Dreamy indie pop, jangly guitars, breathy male vocals, lo-fi warmth, uplifting and whimsical",
        "description": "Dreamy indie pop with jangly guitars and lo-fi warmth.",
        "bpm_range": "110-120",
        "active": True,
    },
    {
        "name": "Afrobeats",
        "prompt_template": "Infectious Afrobeats, log drum, highlife guitars, warm male vocals, danceable, Afro-pop fusion",
        "description": "Infectious Afrobeats with log drums, highlife guitars, and danceable grooves.",
        "bpm_range": "100-110",
        "active": True,
    },
    {
        "name": "K-Pop",
        "prompt_template": "High-energy K-pop dance track, punchy synths, group vocal chant, EDM drop, bright dynamic, catchy",
        "description": "High-energy K-pop dance tracks with punchy synths and group vocals.",
        "bpm_range": "120-130",
        "active": True,
    },
    {
        "name": "Folk / Americana",
        "prompt_template": "Warm Americana folk, fingerpicked acoustic, upright bass, banjo, heartfelt male vocals, storytelling",
        "description": "Warm Americana folk with fingerpicked acoustic, banjo, and storytelling.",
        "bpm_range": "95-105",
        "active": True,
    },
    {
        "name": "Lo-Fi Hip-Hop",
        "prompt_template": "Chill lo-fi hip-hop, vinyl crackle, jazz piano, mellow boom-bap, soft spoken vocals, nostalgic",
        "description": "Chill lo-fi hip-hop with vinyl crackle, jazz piano, and mellow beats.",
        "bpm_range": "75-85",
        "active": True,
    },
    {
        "name": "Funk",
        "prompt_template": "Groovy funk, slap bass, wah-wah guitar, horn stabs, energetic male vocals, party vibe, brass",
        "description": "Groovy funk with slap bass, wah-wah guitar, and horn stabs.",
        "bpm_range": "105-112",
        "active": True,
    },
    {
        "name": "Country Rock",
        "prompt_template": "Country rock anthem, big electric guitars, twangy bends, driving drums, powerful female vocals",
        "description": "Country rock anthems with big electric guitars and twangy bends.",
        "bpm_range": "120-128",
        "active": True,
    },
    {
        "name": "Electropop",
        "prompt_template": "Sparkling electropop, retro 80s synths, pulsing bass, bright breathy female vocal, nostalgic yet modern",
        "description": "Sparkling electropop with retro 80s synths and pulsing bass.",
        "bpm_range": "115-122",
        "active": True,
    },
    {
        "name": "Reggae",
        "prompt_template": "Laid-back reggae, offbeat guitar skanks, deep bass, one-drop rhythm, warm male vocals, sunny vibe",
        "description": "Laid-back reggae with offbeat guitar skanks and one-drop rhythm.",
        "bpm_range": "80-90",
        "active": True,
    },
    {
        "name": "Melodic Rap",
        "prompt_template": "Melodic rap, auto-tune, atmospheric pads, bouncy 808 bass, dreamy hook, emotional male vocals",
        "description": "Melodic rap with auto-tune, atmospheric pads, and bouncy 808 bass.",
        "bpm_range": "130-140",
        "active": True,
    },
    {
        "name": "Tech House",
        "prompt_template": "Driving tech house, rolling bassline, crisp percussion, chopped vocal samples, hypnotic build",
        "description": "Driving tech house with rolling basslines and crisp percussion.",
        "bpm_range": "122-128",
        "active": True,
    },
    {
        "name": "Pop R&B",
        "prompt_template": "Smooth pop R&B, lush piano, soft strings, warm emotional female vocal, mid-tempo groove, intimate",
        "description": "Smooth pop R&B with lush piano, soft strings, and intimate vocals.",
        "bpm_range": "90-100",
        "active": True,
    },
    {
        "name": "Alt-Rock",
        "prompt_template": "Epic alt-rock, quiet verse to massive chorus, layered guitars, soaring emotional male vocal, anthemic",
        "description": "Epic alt-rock with quiet verses building to massive anthemic choruses.",
        "bpm_range": "115-125",
        "active": True,
    },
    {
        "name": "Indie Pop-Rock",
        "prompt_template": "Dreamy indie pop-rock, bright jangly guitars, sweet vocals, lovestruck energy, upbeat and infectious",
        "description": "Dreamy indie pop-rock with bright jangly guitars and lovestruck energy.",
        "bpm_range": "122-135",
        "active": True,
    },
    {
        "name": "Country Spoken Word",
        "prompt_template": "Spoken word country, dry male narrator, simple acoustic guitar, bass, light drums, CB radio feel, deadpan humor",
        "description": "Spoken word country with deadpan humor and CB radio feel.",
        "bpm_range": "90-100",
        "active": True,
    },
    {
        "name": "Comedy Hip-Hop",
        "prompt_template": "Bouncy comedy hip-hop, playful beat, 808 bass, funny confident male vocals, party rap energy",
        "description": "Bouncy comedy hip-hop with playful beats and funny confident vocals.",
        "bpm_range": "125-135",
        "active": True,
    },
]

# ---------------------------------------------------------------------------
# 2. SEED_LORE
# ---------------------------------------------------------------------------

SEED_LORE = [
    {
        "title": "Pronunciation",
        "content": """\
- Yakima → spelled Yak-eh-Mah in all lyrics for correct AI vocal pronunciation""",
        "category": "rules",
        "active": True,
    },
    {
        "title": "YAKIMA FINDS — The Anchor",
        "content": """\
- 15,000 square foot consignment mall and antique business
- Located on 2nd Street in downtown Yakima, WA
- Records, CDs, cassettes, 8-tracks — full music media selection
- Stereo shop in the annex — reel-to-reels, turntables, Marantz, Kenwood, Pioneer, vintage hi-fi gear
- Arcade room — classic arcade machines
- Rock shop — crystals, geodes, minerals
- Local history books and yearbooks
- Kids get a free toy and 2 free books every visit
- Popcorn machine always running
- Consignment booths — every booth is different, like a little world
- Antiques, vintage, collectibles, treasures, one-of-a-kind finds""",
        "category": "places",
        "active": True,
    },
    {
        "title": "RALPH'S ALL THINGS MUSIC & NONSENSE",
        "content": """\
- Guitar store and music shop
- Guitars, amps, and a large variety of instruments
- Full recording studio inside
- Often occupied by a young band jamming or recording
- Located next to / inside the Yakima Finds building
- "Nonsense" in the name — fun, eclectic, personality""",
        "category": "places",
        "active": True,
    },
    {
        "title": "CHURCHILL BOOKS",
        "content": """\
- Jerry — an old hippy, 77 years old, laid-back, friendly, waves from the door
- Jerry loves his weed and grows his own
- Carmen — the smart one, knows every title, finds your book before you ask
- Next door to Yakima Finds
- Used books, rare finds, curated shelves""",
        "category": "places",
        "active": True,
    },
    {
        "title": "BREWS AND CUES",
        "content": """\
- Across the street from Yakima Finds
- Bar with pool tables
- Usually only 1 person working — could be Casey, Logan, Chris, or Mike (pick one per song)
- Wednesday special: Welfare Burger — $4
- Cold beers, good vibes, neighborhood spot""",
        "category": "places",
        "active": True,
    },
    {
        "title": "THREE SISTERS METAPHYSICAL ARTS",
        "content": """\
- On the same block
- Card readings (tarot)
- Spell ingredients — herbs, candles, oils
- Crystals, incense, sage, spiritual goods
- Mystical / witchy vibe""",
        "category": "places",
        "active": True,
    },
    {
        "title": "LA MORENITA BAKERY",
        "content": """\
- Opens early
- Smells amazing — bread, pan dulce, pastries
- The smell drifts down the block
- Coffee, Mexican bakery goods
- Morning anchor of the block""",
        "category": "places",
        "active": True,
    },
    {
        "title": "24-HOUR TACOS",
        "content": """\
- Half a block up from Yakima Finds
- Open 24 hours — late night, early morning, always there
- Quick, cheap, satisfying
- The midnight or after-hours food stop""",
        "category": "places",
        "active": True,
    },
    {
        "title": "BARBER SHOP",
        "content": """\
- On the same block
- Classic barbershop vibes
- Fades, cuts, conversation
- Part of the everyday rhythm of the street""",
        "category": "places",
        "active": True,
    },
    {
        "title": "THE LOTUS ROOM",
        "content": """\
- Traditional pre-funk joint in Yakima — the OG spot
- Owned by Bernadette and Harvey — they've owned it forever
- Harvey is 77 (same age as Jerry)
- Whiskey and BBQ Pork — the go-to order
- "Let's Get Lotusized" — the rallying cry
- Bernadette gets Harvey from the fryer when she sees Jerry coming
- Neighborhood bar, loyalty, history, everyone knows everyone""",
        "category": "places",
        "active": True,
    },
    {
        "title": "KANA WINERY",
        "content": """\
- Another stop on the circuit after the Lotus Room
- Wine spot, social, good vibes""",
        "category": "places",
        "active": True,
    },
    {
        "title": "SHAWN — PIRATE RADIO",
        "content": """\
- Runs his own pirate radio station in the back back room at Churchill Books
- Walks with Jerry after close
- Underground, DIY, rebel energy""",
        "category": "people",
        "active": True,
    },
    {
        "title": "HALLOWEEN LORE",
        "content": """\
- Jerry wore an inflatable dinosaur suit one Halloween
- Had to bend over to get through doors — the suit was huge
- Went to the Lotus Room and bothered everyone with the little T-Rex arms
- Then moved on to Kana Winery for more T-Rex arm chaos
- Classic Jerry energy — lovable, ridiculous, community legend""",
        "category": "events",
        "active": True,
    },
    {
        "title": "SARA SHIELDS",
        "content": """\
- Pretty Sara — together with John (who owns Yakima Finds)
- Reporter for the Yakima Herald — writes and edits the Scene section
- Scene = weekend picks, informing readers of cool happenings around town
- Loves dogs — when she sees a dog she squees so loud it startles the whole room
- Everyone watches and smiles because they see how happy dogs make Sara
- The squee is legendary, joyful, involuntary, pure delight
- Telly is her little good boy (her dog)
- Huge soccer fan — big fan of the Seattle Sounders
- Capo for ECS (Emerald City Supporters)
- Her brother Kyle is the lead supporter — leads the entire stadium in song and cheer, 90 minutes at a time""",
        "category": "people",
        "active": True,
    },
    {
        "title": "JOHN",
        "content": """\
- Owns Yakima Finds
- Together with Sara Shields
- Former MSP owner, 30 years managing technical staff
- Transitioned to retail for quality of life
- Deep technical background, now runs the 15,000 sq ft antique mall""",
        "category": "people",
        "active": True,
    },
    {
        "title": "SONGWRITING RULES",
        "content": """\
- Spell Yakima as "Yak-eh-Mah" in all lyrics
- Lalals prompt field: ≤ 300 characters (genre, tempo, vocal style, instruments, mood)
- Lyrics field: full length OK (verse/chorus/bridge structure works well)
- Not every song needs every business — mix and match 3-5 per song for variety
- Rotate which Brews and Cues person you name — only one per song
- Yakima Finds = the records, stereo gear, antiques, arcade, rock shop, kids stuff
- Ralph's = the instruments, amps, studio, young band""",
        "category": "rules",
        "active": True,
    },
]

# ---------------------------------------------------------------------------
# 3. SEED_SONGS
# ---------------------------------------------------------------------------

SEED_SONGS = [
    # ------------------------------------------------------------------
    # 1. Treasure on Second Street — POP
    # ------------------------------------------------------------------
    {
        "title": "Treasure on Second Street",
        "genre_label": "POP",
        "prompt": "Upbeat synth-pop, bright female vocals, catchy chorus, 120 BPM, shimmering synths, handclaps, feel-good summer energy, radio-ready",
        "lyrics": """\
[Verse 1]
Driving through the valley where the mountains touch the sky
Pulled up on Second Street and something caught my eye
Fifteen thousand square feet of stories left to find
Vinyl in the racks and a Marantz that blew my mind

[Chorus]
Yak-eh-Mah Finds, Yak-eh-Mah Finds
Every aisle another story, every corner shines
Dig a little deeper, see what's left behind
You're gonna lose your heart at Yak-eh-Mah Finds

[Verse 2]
Popcorn popping, eight-tracks stacked beside the CDs on the shelf
Kids get free books and a toy, go find it for yourself
Ralph's got guitars and the amps all cranked up down the hall
Young band in the studio recording through the wall

[Chorus]
Yak-eh-Mah Finds, Yak-eh-Mah Finds
Every aisle another story, every corner shines
Dig a little deeper, see what's left behind
You're gonna lose your heart at Yak-eh-Mah Finds

[Bridge]
La Morenita baking early, smell it down the block
Casey's pouring cold ones over at Brews and Cues nonstop
Three Sisters pulled a card and said the treasure's almost here
Second Street in Yak-eh-Mah, bring everybody near""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 2. Second Street Drip — HIP-HOP
    # ------------------------------------------------------------------
    {
        "title": "Second Street Drip",
        "genre_label": "HIP-HOP",
        "prompt": "Hard trap beat, melodic hook, 808 bass, hi-hats, confident male rap, bouncy rhythm, modern hip-hop, 140 BPM",
        "lyrics": """\
[Hook]
Pull up to the spot, Second Street is where we shop
Yak-eh-Mah Finds got the drip that never stops
Fifteen thousand square feet, yeah we don't quit
Stereo annex Pioneer, that vintage hit

[Verse 1]
Step inside the building, yeah the popcorn hit
Records stacked like gold bars, reel-to-reels legit
Kenwood and the Marantz sitting pretty on the shelf
Turntables and the eight-tracks, find it for yourself
Ralph's next door, every instrument you need
Young band in the studio planting every seed
Arcade room is lit, rock shop full of gleam
Free toys, free books, living out the dream

[Hook]
Pull up to the spot, Second Street is where we shop
Yak-eh-Mah Finds got the drip that never stops

[Verse 2]
Churchill Books next door, Jerry's got the vibes
Carmen pulls the title, she don't need no guide
Crossed the street to Brews and Cues, Logan's got the pour
Wednesday welfare burger, four bucks, nothing more
Three Sisters reading futures in the afternoon
La Morenita baking bread beneath the valley moon
Twenty-four-hour tacos when the night gets late
Second Street in Yak-eh-Mah, can't nobody hate""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 3. Dig Through the Past — ROCK
    # ------------------------------------------------------------------
    {
        "title": "Dig Through the Past",
        "genre_label": "ROCK",
        "prompt": "Driving arena rock, electric guitars, powerful drums, big chorus gang vocals, gritty male lead, 130 BPM",
        "lyrics": """\
[Verse 1]
Roll into the valley with the windows down
Best kept secret block in any small-town sound
Second Street is calling like a siren song
Reel-to-reel is spinning, come and sing along

[Pre-Chorus]
Ralph's got guitars hanging, amps are cranked up loud
Young band in the studio, drawing in a crowd

[Chorus]
Dig through the past at Yak-eh-Mah Finds
Every dusty corner hides a golden mine
Rock and roll is living on these shelves tonight
Yak-eh-Mah Finds, we're bringing it to life

[Verse 2]
Vinyl stacked with Zeppelin, Sabbath on the rack
Eight-tracks and cassettes, yeah we're bringing it back
Stereo annex glowing, Pioneer and Kenwood dreams
Turntables for the taking, nothing's what it seems

[Chorus]
Dig through the past at Yak-eh-Mah Finds
Every dusty corner hides a golden mine
Rock and roll is living on these shelves tonight
Yak-eh-Mah Finds, we're bringing it to life

[Bridge]
Kids walking out with free books and toys in hand
Chris poured me a cold one at the Brews and Cues stand
Three Sisters shuffling cards underneath the neon glow
Twenty-four-hour tacos waiting down below""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 4. That Old Familiar Feeling — COUNTRY
    # ------------------------------------------------------------------
    {
        "title": "That Old Familiar Feeling",
        "genre_label": "COUNTRY",
        "prompt": "Modern country pop, acoustic guitar, warm male vocals, storytelling, singalong chorus, slide guitar, fiddle, 110 BPM",
        "lyrics": """\
[Verse 1]
Took a drive through Yak-eh-Mah on a Saturday morn
Parked on Second Street where the good stuff's born
Walked inside and the popcorn filled the air
Found a Pioneer turntable sitting there

[Chorus]
That old familiar feeling when you find the one
A record you been searching for since ninety-one
Books and toys for the little ones, they run for free
Yak-eh-Mah Finds is where I'm meant to be

[Verse 2]
Ralph's had a Telecaster hanging on the wall
Young band in the studio, heard them through the hall
Popped next door to Churchill Books, Jerry waved me in
Carmen said "I got the one," with that knowing grin

[Chorus]
That old familiar feeling when you find the one
A record you been searching for since ninety-one
Books and toys for the little ones, they run for free
Yak-eh-Mah Finds is where I'm meant to be

[Bridge]
Crossed to Brews and Cues, Mike cracked a cold one quick
Wednesday welfare burger, four bucks did the trick
La Morenita's bread was rising down the block
Three Sisters pulled a card and said I shouldn't stop""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 5. Encuentra en Yak-eh-Mah — LATIN / REGGAETON
    # ------------------------------------------------------------------
    {
        "title": "Encuentra en Yak-eh-Mah",
        "genre_label": "LATIN / REGGAETON",
        "prompt": "Reggaeton dembow beat, bilingual hook, tropical synths, Latin pop energy, male vocals, 95 BPM, urban Latin",
        "lyrics": """\
[Chorus]
Encuentra, encuentra, at Yak-eh-Mah Finds
Second Street is bumping, yeah we're feeling fine
Treasure in the valley, come and take your time
Yak-eh-Mah Finds, dale, that's the vibe

[Verse 1]
Downtown in the valley where the sun is shining bright
Walk into the building and it feels so right
Fifteen thousand square feet, cassettes and vinyl stacked
Stereo annex Marantz, yeah we got it like that
La Morenita baking pan dulce down the way
Twenty-four-hour tacos keep you fed night and day

[Chorus]
Encuentra, encuentra, at Yak-eh-Mah Finds
Second Street is bumping, yeah we're feeling fine
Treasure in the valley, come and take your time
Yak-eh-Mah Finds, dale, that's the vibe

[Verse 2]
Ralph's got every instrument you could ever dream
Young band laying tracks, studio's a machine
Churchill Books is open, Carmen knows the way
Logan poured a cold one at the end of the day
Three Sisters reading cards for the magic that you seek
Barbershop is fresh, this block can't be beat""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 6. Find It (Second Street Drop) — EDM / DANCE
    # ------------------------------------------------------------------
    {
        "title": "Find It (Second Street Drop)",
        "genre_label": "EDM / DANCE",
        "prompt": "High energy EDM anthem, big synth build and drop, female vocal chops, four-on-the-floor, future rave, 128 BPM",
        "lyrics": """\
[Verse]
Come with me to Yak-eh-Mah
Second Street is where we are
Treasures hiding everywhere
Fifteen thousand feet to share

[Pre-Drop]
Turntables spinning, lights are flashing
Arcade games and crystals crashing
Find it, find it, find it now
Yak-eh-Mah is showing how

[Chorus/Drop]
Yak-eh-Mah Finds, find it, find it
Yak-eh-Mah Finds, find it, find it
Every aisle a brand new story
Yak-eh-Mah Finds in all its glory

[Build]
Reel-to-reel and Pioneer
Ralph's got the band, they're jamming here
La Morenita, bread is glowing
Three Sisters, the future's showing
Tacos at 3am are calling
Second Street we're never falling

[Chorus/Drop]
Yak-eh-Mah Finds, find it, find it
Yak-eh-Mah Finds, find it, find it""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 7. Something Beautiful — R&B / SOUL
    # ------------------------------------------------------------------
    {
        "title": "Something Beautiful",
        "genre_label": "R&B / SOUL",
        "prompt": "Smooth neo-soul, Rhodes piano, mellow bass, silky female vocals, lush harmonies, 90 BPM, vintage soul meets modern R&B",
        "lyrics": """\
[Verse 1]
Took a slow ride through the valley on a lazy afternoon
Found my way to Second Street beneath the autumn moon
Something pulled me through those doors, I swear it felt like fate
Reel-to-reel was playing Motown, baby it was worth the wait

[Chorus]
Something beautiful is waiting there for you
At Yak-eh-Mah Finds where everything feels true
A love song on the turntable from another time
Something beautiful is always there to find

[Verse 2]
La Morenita's bread was drifting through the morning air
Churchill Books had candles in the window, Jerry in his chair
Carmen stacked the shelves like poetry in every row
Three Sisters read my palm and said there's more than I could know

[Chorus]
Something beautiful is waiting there for you
At Yak-eh-Mah Finds where everything feels true
A love song on the turntable from another time
Something beautiful is always there to find

[Outro]
Casey poured it slow at Brews and Cues at golden hour
Barbershop was humming, fading like a flower
Second Street in Yak-eh-Mah, the valley's finest gem
Every time I walk this block, I fall in love again""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 8. Little Wonders — INDIE POP
    # ------------------------------------------------------------------
    {
        "title": "Little Wonders",
        "genre_label": "INDIE POP",
        "prompt": "Dreamy indie pop, jangly guitars, breathy male vocals, lo-fi warmth, uplifting and whimsical, 115 BPM",
        "lyrics": """\
[Verse 1]
I wandered down to Second Street on a whim
Sunlight through the windows, the day was growing dim
But inside Yak-eh-Mah Finds the world was glowing bright
A Kenwood receiver catching all the light

[Chorus]
Little wonders, little wonders all around
Yak-eh-Mah Finds is the best thing that I found
Fifteen thousand square feet of someone else's dreams
Nothing's ever quite exactly what it seems

[Verse 2]
Cassettes beside the vinyl, eight-tracks in a row
Popcorn in the air and the arcade's got its glow
Kids walked out with free books, two toys in their hands
Ralph's got a young band tracking drums and making plans

[Chorus]
Little wonders, little wonders all around
Yak-eh-Mah Finds is the best thing that I found

[Bridge]
Three Sisters shuffling tarot underneath a velvet sign
La Morenita's ovens warming up at half past nine
Jerry at Churchill's smiling like he always does
Carmen knows the answer, that's just what she was
Chris had Brews and Cues all to himself today
Second Street in Yak-eh-Mah, that's just how we play""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 9. Come Find Am — AFROBEATS
    # ------------------------------------------------------------------
    {
        "title": "Come Find Am",
        "genre_label": "AFROBEATS",
        "prompt": "Infectious Afrobeats, log drum, highlife guitars, warm male vocals, danceable, Afro-pop fusion, 105 BPM",
        "lyrics": """\
[Chorus]
Come and find it at Yak-eh-Mah
Second Street we go far far
Treasures shining like a star
Yak-eh-Mah Finds, oh here we are

[Verse 1]
Everybody come together, move your body to the beat
Fifteen thousand square feet and the energy is sweet
Popcorn popping in the corner, vinyl going round
Stereo annex bumping with that Pioneer sound
Rock shop full of crystals, arcade games alive
Free books and a toy for every kid that walks inside

[Chorus]
Come and find it at Yak-eh-Mah
Second Street we go far far
Treasures shining like a star
Yak-eh-Mah Finds, oh here we are

[Verse 2]
Ralph's got guitars and a studio that shakes the ground
Young band cutting tracks, making the most beautiful sound
Churchill Books is open, Jerry dancing in the aisle
Carmen found your book and she been holding it a while
La Morenita's bread is golden, twenty-four-hour tacos call
Mike's at Brews and Cues tonight, taking care of all""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 10. FIND! FIND! FIND! — K-POP
    # ------------------------------------------------------------------
    {
        "title": "FIND! FIND! FIND!",
        "genre_label": "K-POP",
        "prompt": "High-energy K-pop dance track, punchy synths, group vocal chant, EDM drop, bright dynamic, 125 BPM, catchy",
        "lyrics": """\
[Intro Chant]
Find! Find! Find! At Yak-eh-Mah!
Find! Find! Find! You're a star!

[Verse 1]
Walking through the door and the vibe is on
Second Street in Yak-eh-Mah, we go all day long
Fifteen thousand feet, turntables and CDs too
Marantz in the annex, everything is new to you

[Pre-Chorus]
Popcorn, records, crystals glow
Ralph's young band putting on a show

[Chorus]
Find! Find! Find! At Yak-eh-Mah Finds
Every treasure's one of a kind
Find! Find! Find! Leave the world behind
Yak-eh-Mah Finds blows your mind

[Verse 2]
Arcade lights are flashing, rock shop's looking bright
Kids got free books in their hands, squeezing toys so tight
Three Sisters reading cards behind a velvet curtain
La Morenita smells so good, one thing is for certain
This block's got the magic and the barbershop's a glow
Second Street is everything, now everybody knows

[Chorus]
Find! Find! Find! At Yak-eh-Mah Finds
Every treasure's one of a kind
Find! Find! Find! Leave the world behind
Yak-eh-Mah Finds blows your mind""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 11. Down on Second Street — FOLK / AMERICANA
    # ------------------------------------------------------------------
    {
        "title": "Down on Second Street",
        "genre_label": "FOLK / AMERICANA",
        "prompt": "Warm Americana folk, fingerpicked acoustic, upright bass, banjo, heartfelt male vocals, storytelling, 100 BPM",
        "lyrics": """\
[Verse 1]
There's a block on Second Street in a valley town
Where the mountains keep their secrets and the sun comes down
Fifteen thousand square feet, every board's got soul
Yak-eh-Mah Finds is where the stories make you whole

[Chorus]
Down on Second Street the past ain't really gone
Every record, every reel-to-reel is singing its own song
Kids are leaving happy, popcorn in the air
Down on Second Street there's treasure everywhere

[Verse 2]
Found my grandfather's yearbook on a dusty shelf
A Pioneer receiver talking to itself
Jerry at Churchill's is an old hippy with a grin
Carmen's the smart one, she'll tell you where to begin

[Chorus]
Down on Second Street the past ain't really gone
Every record, every reel-to-reel is singing its own song

[Verse 3]
Ralph's got instruments from floor to ceiling stacked
Young band in the studio, laying down a track
Three Sisters read my cards and told me what I'd find
La Morenita's ovens warming up the morning kind
Logan's minding Brews and Cues, a quiet afternoon
Barbershop is buzzing underneath the valley moon""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 12. Yak-eh-Mah Afternoons — LO-FI HIP-HOP
    # ------------------------------------------------------------------
    {
        "title": "Yak-eh-Mah Afternoons",
        "genre_label": "LO-FI HIP-HOP",
        "prompt": "Chill lo-fi hip-hop, vinyl crackle, jazz piano, mellow boom-bap, soft spoken vocals, nostalgic, 80 BPM",
        "lyrics": """\
[Verse 1]
Slow day in the valley, sun is getting low
Second Street in Yak-eh-Mah, nowhere else to go
Step inside the building, let the worries fade
Popcorn and a turntable, in the shade we made
Kenwood amp is humming warm and orange in the dark
Fifteen thousand square feet like a quiet park

[Chorus]
Yak-eh-Mah afternoons, drifting through the past
Every find a memory, built to always last
Yak-eh-Mah afternoons, treasures all around
Second Street is where the peace is always found

[Verse 2]
Flip through old yearbooks in the corner by the door
Crystal in the rock shop that you can't ignore
Churchill Books is quiet, Jerry sipping tea
Carmen filing paperbacks alphabetically
Ralph's studio is empty, amps still warm from noon
Somebody left an eight-track playing Coltrane in the room

[Outro]
Casey wiping down the bar at Brews and Cues alone
Wednesday welfare burger smell is drifting through the zone
Tacos on the corner underneath the evening star
Yak-eh-Mah afternoons, perfect as they are""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 13. Get Down at the Finds — FUNK
    # ------------------------------------------------------------------
    {
        "title": "Get Down at the Finds",
        "genre_label": "FUNK",
        "prompt": "Groovy funk, slap bass, wah-wah guitar, horn stabs, energetic male vocals, party vibe, 108 BPM, brass",
        "lyrics": """\
[Verse 1]
Uh, come on, let me take you somewhere funky now
Second Street in Yak-eh-Mah, we gonna show you how
Fifteen thousand square feet of the grooviest place in town
Reel-to-reels and Marantz gear, we never let you down

[Chorus]
Get down, get down at the Finds
Yak-eh-Mah got the treasure every single time
Get down, get down, feel the groove
Vinyl spinning, arcade bumping, get into the move

[Verse 2]
Popcorn popping to the beat, kids are dancing free
Two free books and a toy, that's the guarantee
Ralph's got a bass guitar that's begging to be played
Young band in the studio, hits are getting made

[Chorus]
Get down, get down at the Finds
Yak-eh-Mah got the treasure every single time

[Bridge]
Mike's at Brews and Cues tonight, cold ones on the pour
Wednesday welfare burger, four bucks out the door
Three Sisters got the magic, cards are on the table
La Morenita's kitchen, fresh as they are able
Jerry's selling books and Carmen's stacking shelves
Second Street is funky and it speaks for itself""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 14. Valley Gold — COUNTRY ROCK
    # ------------------------------------------------------------------
    {
        "title": "Valley Gold",
        "genre_label": "COUNTRY ROCK",
        "prompt": "Country rock anthem, big electric guitars, twangy bends, driving drums, powerful female vocals, 125 BPM",
        "lyrics": """\
[Verse 1]
I hit the highway headed for the valley sun
Heard about a block on Second Street where everybody runs
Biggest antique mall this side of the Cascade Range
Fifteen thousand square feet and nothing feels the same

[Chorus]
Valley gold, valley gold, that's what they call it here
Yak-eh-Mah Finds got the treasures year to year
From the records to the rock shop, every story's told
Second Street's got something better, call it valley gold

[Verse 2]
Ralph's had a six-string that was begging me to stay
Young band in the studio making noise all day
Stereo annex had a Pioneer that caught my eye
Turntable so beautiful it almost made me cry

[Chorus]
Valley gold, valley gold, that's what they call it here
Yak-eh-Mah Finds got the treasures year to year

[Bridge]
Logan's minding Brews and Cues, poured me something cold
Churchill Books had Jerry saying "This one's solid gold"
La Morenita's bread was rising in the early light
Tacos twenty-four-seven, keeping Second Street right""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 15. Lost and Found — ELECTROPOP
    # ------------------------------------------------------------------
    {
        "title": "Lost and Found",
        "genre_label": "ELECTROPOP",
        "prompt": "Sparkling electropop, retro 80s synths, pulsing bass, bright breathy female vocal, nostalgic yet modern, 118 BPM",
        "lyrics": """\
[Verse 1]
Neon lights and dusty shelves under one big roof
Every piece has got a past, every scratch is proof
Second Street in Yak-eh-Mah, feel the magic start
Fifteen thousand square feet is a work of art

[Pre-Chorus]
Lost things find their way to you
Everything old is something new

[Chorus]
Lost and found at Yak-eh-Mah Finds
Dancing through the aisles, we're losing track of time
Lost and found, we leave the world behind
Everything we needed was already there to find

[Verse 2]
Cassettes beside the vinyl, Marantz in the back
Reel-to-reel still threaded up on someone's dusty track
Ralph's guitars are gleaming and the studio's alive
Young band cutting demos just to feel that live

[Chorus]
Lost and found at Yak-eh-Mah Finds
Dancing through the aisles, we're losing track of time

[Bridge]
Churchill Books is glowing, Carmen's in the zone
Brews and Cues at midnight, Casey's on her own
Barbershop and tacos open after dark
Second Street's the kind of block that lights up like a spark""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 16. Irie on Second Street — REGGAE
    # ------------------------------------------------------------------
    {
        "title": "Irie on Second Street",
        "genre_label": "REGGAE",
        "prompt": "Laid-back reggae, offbeat guitar skanks, deep bass, one-drop rhythm, warm male vocals, sunny vibe, 85 BPM",
        "lyrics": """\
[Verse 1]
Take it easy now, come on down the road
Second Street in Yak-eh-Mah, lighten up your load
Fifteen thousand square feet of good vibrations here
Popcorn and the vinyl, nothing left to fear

[Chorus]
Irie, irie on Second Street
Yak-eh-Mah Finds make the day complete
Treasures for the people, music for the soul
Come and feel the rhythm, let the good times roll

[Verse 2]
Turntable is spinning something sweet and slow
Kenwood amp is glowing with that golden glow
Ralph's got instruments from every corner of the earth
Young band in the studio finding out what music's worth

[Chorus]
Irie, irie on Second Street
Yak-eh-Mah Finds make the day complete

[Verse 3]
Churchill's got the reading, Jerry's kicking back
Carmen's organizing like a beautiful attack
Three Sisters burning something sweet into the breeze
Chris is pouring cold ones, putting everybody at ease
La Morenita's open early, barbershop runs late
Second Street in Yak-eh-Mah, can't nobody hate""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 17. Hidden Gems — MELODIC RAP
    # ------------------------------------------------------------------
    {
        "title": "Hidden Gems",
        "genre_label": "MELODIC RAP",
        "prompt": "Melodic rap, auto-tune, atmospheric pads, bouncy 808 bass, dreamy hook, emotional male vocals, 135 BPM",
        "lyrics": """\
[Hook]
Hidden gems in Yak-eh-Mah, yeah we shine so bright
Second Street on a Saturday night
Fifteen thousand square feet of the things you love
Yak-eh-Mah Finds, it's the place I'm thinking of

[Verse 1]
Pull up to the valley and the mountains fade to gold
Step inside the Finds and let the stories all unfold
Stereo annex stacked with gear from back in the day
Marantz and the reel-to-reels just blowing me away
Rock shop full of crystals, can't believe the things they hid
Arcade lit up like a movie, free books for every kid
Popcorn in the air got me feeling something real
Ralph's got a young band in the studio cutting steel

[Hook]
Hidden gems in Yak-eh-Mah, yeah we shine so bright
Second Street on a Saturday night

[Verse 2]
Jerry's at Churchill's, old hippy with the wisdom
Carmen's got the titles, never miss 'em
Three Sisters reading cards underneath the moon
La Morenita's kitchen smelling like a honeymoon
Casey's got the Brews and Cues, welfare burger Wednesday night
Four bucks and a cold one, yeah the price is right
Twenty-four-hour tacos, barbershop's a glow
Yak-eh-Mah Finds on Second Street, the only place to go""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 18. The Find (Club Mix) — TECH HOUSE
    # ------------------------------------------------------------------
    {
        "title": "The Find (Club Mix)",
        "genre_label": "TECH HOUSE",
        "prompt": "Driving tech house, rolling bassline, crisp percussion, chopped vocal samples, hypnotic build, 126 BPM",
        "lyrics": """\
[Vocal Hook - repeat and chop]
Find it, find it at Yak-eh-Mah
Find it, find it, that's where we are
Second Street, the beat don't stop
Fifteen thousand feet and we're over the top

[Verse]
Come to the valley where the bass hits right
Yak-eh-Mah Finds open every night
Turntables spinning, Pioneer on the wall
Reel-to-reel and Kenwood, come and take it all

[Drop Hook]
Yak-eh-Mah, find it
Yak-eh-Mah, find it
Second Street, find it
Can't be beat, find it

[Build]
Ralph's studio is shaking with a brand new sound
Three Sisters, La Morenita, tacos going round
Logan's at the bar tonight, the block is all alive
Yak-eh-Mah Finds on Second Street, we thrive""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 19. Take Me There — POP R&B
    # ------------------------------------------------------------------
    {
        "title": "Take Me There",
        "genre_label": "POP R&B",
        "prompt": "Smooth pop R&B, lush piano, soft strings, warm emotional female vocal, mid-tempo groove, 95 BPM, intimate",
        "lyrics": """\
[Verse 1]
I've been looking for a place that feels like coming home
Somewhere I can wander and never feel alone
Then I found it on Second Street, through a big front door
Yak-eh-Mah Finds had everything and so much more

[Chorus]
Take me there, take me back to Yak-eh-Mah
Where the records play and a Marantz hums from far
Fifteen thousand square feet of someone else's love
Take me there, it's all I'm dreaming of

[Verse 2]
Popcorn in the air and free books in every hand
Kids are leaving happy, isn't that just grand
Jerry waved from Churchill's, Carmen found my book
Ralph's young band was playing, said "Come take a look"

[Chorus]
Take me there, take me back to Yak-eh-Mah
Where the records play and a Marantz hums from far

[Bridge]
La Morenita's open early, smell it down the way
Twenty-four-hour tacos when you need to end your day
Mike's at Brews and Cues tonight, knows my name by heart
Barbershop is fresh, the block's a work of art
Three Sisters lit a candle, said some words I didn't know
Take me there, take me back to Second Street's glow""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 20. Fifteen Thousand Stories — ALT-ROCK
    # ------------------------------------------------------------------
    {
        "title": "Fifteen Thousand Stories",
        "genre_label": "ALT-ROCK",
        "prompt": "Epic alt-rock, quiet verse to massive chorus, layered guitars, soaring emotional male vocal, 120 BPM, anthemic",
        "lyrics": """\
[Verse 1 - quiet, building]
In the shadow of the Cascades where the river runs
There's a block on Second Street that belongs to everyone
Fifteen thousand square feet holding fifteen thousand dreams
And nothing in Yak-eh-Mah is ever what it seems

[Chorus - massive]
Fifteen thousand stories waiting to be told
Every record, every reel-to-reel worth its weight in gold
We are the finders, we are the seekers of the light
Yak-eh-Mah Finds is burning bright tonight

[Verse 2]
Stereo annex glowing, Pioneer and Kenwood stacked
Turntables for the dreamers and the vinyl's all intact
Ralph's got guitars and amps that shake the building's bones
Young band in the studio turning silence into songs

[Chorus]
Fifteen thousand stories waiting to be told
Every record, every reel-to-reel worth its weight in gold
We are the finders, we are the seekers of the light
Yak-eh-Mah Finds is burning bright tonight

[Bridge - build to finale]
Jerry's an old hippy keeping Churchill Books alive
Carmen knows the title of the book before you arrive
Three Sisters cast the spell that keeps this block awake
La Morenita's bread is proof that mornings never break
Casey's at the bar alone, welfare burger Wednesday night
Tacos never close, and the barbershop's got the light
Free books, free toys, and the popcorn's in the air
Yak-eh-Mah Finds on Second Street, we'll always be there""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 21. The Dinosaur on Second Street — COUNTRY (Full Story)
    # ------------------------------------------------------------------
    {
        "title": "The Dinosaur on Second Street",
        "genre_label": "COUNTRY",
        "prompt": "Fun upbeat country storytelling, acoustic guitar, fiddle, playful male vocals, honky-tonk bounce, 115 BPM, novelty anthem",
        "lyrics": """\
[Verse 1]
Now Jerry's seventy-seven, sells books on Second Street
Old hippy with a handshake and a smile you can't beat
But Halloween he showed up in an inflatable dinosaur
Had to bend down through the doorway, couldn't fit through Churchill's door
Carmen shook her head and laughed, Shawn turned off the radio
The pirate broadcast wrapped up early for the dino show

[Chorus]
Jerry's in a dinosaur suit stomping down the block
Little T-Rex arms just swinging, won't nobody talk
Bending through the doorways like a seventy-seven-year-old king
If you were on Second Street that night you saw the whole damn thing

[Verse 2]
After close him and Shawn went walking to the Lotus Room
Bernadette looked out the window, said "Oh Lord, here comes the goon"
She pulled Harvey from the fryer, said "Your best friend's here again"
Harvey's seventy-seven too, just wiped his hands and grinned
Jerry walked up to the bar, the little arms went wild
Poking every customer like a misbehaving child

[Chorus]
Jerry's in a dinosaur suit stomping down the block
Little T-Rex arms just swinging, won't nobody talk
Bending through the doorways like a seventy-seven-year-old king
If you were on Second Street that night you saw the whole damn thing

[Bridge]
Whiskey and the BBQ pork, that's the Lotus way
Bernadette and Harvey been pouring every single day
"Let's get Lotusized!" Jerry yelled with the arms flapping free
Then he waddled off to Kana Winery
More wine, more arms, more people getting squeezed
Just another Halloween in Yak-eh-Mah if you please

[Outro]
Now they talk about that dinosaur every single year
The night old Jerry terrorized the town with love and beer
Second Street remembers and it always tells the tale
A seventy-seven-year-old hippy in a dino on the trail""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 22. Little Arms — FUNK (Dinosaur Chaos Party)
    # ------------------------------------------------------------------
    {
        "title": "Little Arms",
        "genre_label": "FUNK",
        "prompt": "Groovy funk, slap bass, horn stabs, wah-wah guitar, playful male vocals, party energy, 110 BPM, brass section",
        "lyrics": """\
[Verse 1]
Uh, let me tell you bout a man named Jerry
Seventy-seven years old and extraordinarily scary
Halloween night, inflatable dinosaur on
Had to bend through every doorway from the dusk until the dawn
Shawn shut down the pirate radio, said "I gotta see this"
They locked up Churchill Books and hit the street on a mission

[Chorus]
Little arms, little arms, Jerry's got the little arms
Squeezing everybody at the bar with dinosaur charm
Little arms, little arms, swinging left and right
Yak-eh-Mah ain't never had a funkier night

[Verse 2]
Walked into the Lotus Room, Bernadette just screamed
Pulled Harvey from the fryer, said "It's worse than what I dreamed"
Harvey's seventy-seven too, he don't even flinch
Jerry's poking every patron, inch by inch by inch
Whiskey and the BBQ pork, the suit is getting sweaty
Bernadette said "Get Lotusized" but nobody was ready

[Chorus]
Little arms, little arms, Jerry's got the little arms
Squeezing everybody at the bar with dinosaur charm
Little arms, little arms, swinging left and right
Yak-eh-Mah ain't never had a funkier night

[Bridge]
He wasn't done, oh no, he waddled to Kana Winery
More arms, more squeezing, more inflatable chicanery
Seventy-seven in a dino suit, what a beautiful sight
Let's get Lotusized, let's get Lotusized tonight""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 23. Dino on the Loose — INDIE ROCK
    # ------------------------------------------------------------------
    {
        "title": "Dino on the Loose",
        "genre_label": "INDIE ROCK",
        "prompt": "Upbeat indie rock, jangly guitars, driving drums, playful male vocals, anthemic chorus, 122 BPM, festival energy",
        "lyrics": """\
[Verse 1]
Halloween on Second Street, the whole block's dressed to kill
La Morenita's got skull cookies on the windowsill
Three Sisters burning something strange, the smoke is turning green
Ralph's young band is playing covers of a horror movie scene
But everybody's talking bout the dinosaur outside
Old Jerry from the bookstore bending sideways just to slide
Through the door of Churchill Books where Shawn's got pirate radio
Carmen handed out the candy, said "Just let the madman go"

[Chorus]
There's a dino on the loose on Second Street tonight
Seventy-seven years of hippy with the arms swinging right
Yak-eh-Mah on Halloween, you never know what's coming through
There's a dino on the loose and he's coming after you

[Verse 2]
After close they hit the Lotus, Shawn and Jerry side by side
Bernadette saw the dinosaur and almost tried to hide
She got Harvey from the fryer, said "Your boy is back again"
Harvey shook his head and poured the whiskey to the brim
BBQ pork and little arms flapping through the crowd
Jerry got the whole bar laughing, got the whole bar loud
"Let's get Lotusized!" he shouted with his tiny hands
Then waddled out to Kana Winery with even bigger plans

[Chorus]
There's a dino on the loose on Second Street tonight
Seventy-seven years of hippy with the arms swinging right
Yak-eh-Mah on Halloween, you never know what's coming through
There's a dino on the loose and he's coming after you

[Bridge]
Kids got free books at the Finds and popcorn in their bags
Brews and Cues had cobwebs, Casey wearing monster rags
But nothing on this block could top the sight of Jerry's walk
A dinosaur who couldn't fit through doors but wouldn't stop to talk""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 24. Rex in Yak-eh-Mah — HIP-HOP (Comedy Rap)
    # ------------------------------------------------------------------
    {
        "title": "Rex in Yak-eh-Mah",
        "genre_label": "HIP-HOP",
        "prompt": "Bouncy comedy hip-hop, playful beat, 808 bass, funny confident male vocals, party rap energy, 130 BPM",
        "lyrics": """\
[Hook]
Jerry in the dino suit, look at him go
Seventy-seven with the little arms stealing the show
Lotus Room to Kana, he ain't done yet
Yak-eh-Mah Halloween, best one you can get

[Verse 1]
Picture this, a Tuesday night, October thirty-one
Jerry showed up to the bookstore like a prehistoric son
Inflatable dinosaur, the green one, blowing up
Couldn't even fit through the door without a duck
Shawn was in the back room spinning pirate radio
Saw the dino shadow, said "Aight, let's end the show"
Carmen locked the register, the candy bowl was done
They hit Second Street, the dinosaur had just begun
Passing Yak-eh-Mah Finds, the arcade kids went wild
Popcorn and a dinosaur, every single child
Free books in one hand, pointing with the other
"Mama, is that a real one?" "No baby, that's the book man's brother"

[Hook]
Jerry in the dino suit, look at him go
Seventy-seven with the little arms stealing the show

[Verse 2]
Rolled into the Lotus Room, bent through the front door
Bernadette dropped a plate, said "Not this dinosaur"
Got Harvey from the fryer, grease still on his hands
Harvey's seventy-seven too, he understands
Jerry hit the bar, little arms just going crazy
Poking every shoulder, every elbow, getting hazy
Whiskey and the BBQ pork, suit is fogging up
"Let's get Lotusized!" holding up a tiny cup
He wasn't satisfied, he needed one more spot
Waddled to Kana Winery, gave 'em all he got
Little arms on wine people, squeaking with each squeeze
A dinosaur from Second Street just doing what he please

[Outro]
Bernadette and Harvey been running Lotus forever
The pre-funk joint in Yak-eh-Mah, there ain't nothing better
But Halloween belongs to Jerry and his little arms
A seventy-seven-year-old dino spreading Yak-eh-Mah charm""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 25. Let's Get Lotusized — POP ROCK
    # ------------------------------------------------------------------
    {
        "title": "Let's Get Lotusized",
        "genre_label": "POP ROCK",
        "prompt": "Big pop rock anthem, electric guitars, sing-along chorus, energetic mixed vocals, 124 BPM, arena party feel",
        "lyrics": """\
[Verse 1]
Friday night on Second Street and the whole town's coming out
Yak-eh-Mah Finds just closed up, popcorn still floating about
Ralph's band is loading out the studio door
Shawn's pirate radio signing off, it's time for something more
Churchill Books is dark but the block is just waking up
La Morenita's closed but the Lotus Room is filling cups

[Chorus]
Let's get Lotusized, let's get Lotusized tonight
Bernadette and Harvey got the whiskey pouring right
BBQ pork and good people, Second Street's alive
Let's get Lotusized, let's get Lotusized tonight

[Verse 2]
Now you should have seen it back on Halloween last year
Jerry showed up in a dinosaur, the whole block disappeared
Seventy-seven in a dino suit, bending through the door
Little T-Rex arms on everybody on the floor
Shawn just walked behind him like a handler for a beast
Harvey saw him coming, said "Oh great, we'll never feast in peace"

[Chorus]
Let's get Lotusized, let's get Lotusized tonight
Bernadette and Harvey got the whiskey pouring right
BBQ pork and good people, Second Street's alive
Let's get Lotusized, let's get Lotusized tonight

[Bridge]
Three Sisters said the cards predicted chaos on this night
Casey at Brews and Cues just shook his head, "That's right"
Kana Winery got the dinosaur by ten o'clock
Twenty-four-hour tacos fed the legend of the block
You don't have to be a dino to get Lotusized with us
Just show up to Second Street in Yak-eh-Mah and trust

[Final Chorus]
Let's get Lotusized, let's get Lotusized tonight
Bernadette and Harvey got the whiskey pouring right
Jerry's little arms are reaching for you in the crowd
Let's get Lotusized, Second Street is loud""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 26. Classified: One Dinosaur, Slightly Used — COUNTRY SPOKEN WORD
    # ------------------------------------------------------------------
    {
        "title": "Classified: One Dinosaur, Slightly Used",
        "genre_label": "COUNTRY SPOKEN WORD",
        "prompt": "Spoken word country, dry male narrator, simple acoustic guitar, bass, light drums, CB radio feel, 95 BPM, deadpan humor",
        "lyrics": """\
[Spoken - Verse 1]
For sale: One inflatable dinosaur suit, green, adult size
Previously owned by a seventy-seven-year-old hippy
Who grows his own weed on the side of a hill
And sells used books on Second Street in Yak-eh-Mah, Washington
Suit's in fair condition
Got a crease in the neck from bending through doorways
Which he had to do
On account of the suit being nine feet tall
And the doors at Churchill Books being six foot eight
Carmen measured

[Spoken - Verse 2]
Subject last seen Halloween night
Walking south on Second Street with one Shawn
Who runs a pirate radio station
Out of the back back room of the bookstore
Nobody knows what frequency
Nobody's asked
They locked up the books around nine
Jerry was still in the suit
Shawn did not ask why
They walked to the Lotus Room
Which is the pre-funk joint in Yak-eh-Mah
Has been forever
Will be forever
That's just a fact

[Spoken - Verse 3]
Upon arrival at the Lotus Room
Bernadette looked out the window
And said a word we can't repeat on the radio
Then she went and got Harvey from the fryer
Harvey is also seventy-seven
Same as Jerry
They have known each other a long time
Harvey wiped his hands on his apron
Poured two whiskeys
Set out the BBQ pork
And waited for the inevitable

[Spoken - Verse 4]
The inevitable being Jerry
Working the room with the little arms
Now if you've never been accosted by a seventy-seven-year-old man
In an inflatable dinosaur suit
With two-foot rubber arms
In a bar that smells like whiskey and smoked pork
Well
You haven't been to the Lotus Room on Halloween
Bernadette says "Let's get Lotusized"
Harvey says nothing
Harvey has seen a lot of things from behind that fryer

[Spoken - Verse 5]
After sufficient Lotusizing
Jerry decided Kana Winery needed the same treatment
So he walked there
Still in the suit
Still with the little arms
Shawn walked behind him
Not in a suit
Just in solidarity
The wine people were not prepared
There's no way to prepare
You just accept the arms
And move on with your evening

[Spoken - Outro]
So if anyone wants an inflatable dinosaur suit
Green, size large
Smells a little like whiskey, BBQ pork, and the good stuff Jerry grows
Crease in the neck, sweat stain on the inside
Contact Churchill Books, Second Street, Yak-eh-Mah
Ask for Jerry
He's the old hippy
You can't miss him
He's the one who looks like he's done this before
Because he has
He will again
That's just how it works on Second Street""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 27. Can't Stop Looking — INDIE POP-ROCK
    # ------------------------------------------------------------------
    {
        "title": "Can't Stop Looking",
        "genre_label": "INDIE POP-ROCK",
        "prompt": "Dreamy indie pop-rock, bright jangly guitars, sweet female vocals, lovestruck energy, upbeat and infectious, 128 BPM, Beach Bunny vibes",
        "lyrics": """\
[Verse 1]
He's supposed to be sorting through the vinyl in the back
Marantz on the counter and a box of eight-tracks to unpack
But she walked through the door with coffee and that smile
And now he's standing frozen in the middle of the aisle
She's writing up the Scene section on her phone between the shelves
Weekend picks for Yak-eh-Mah, she makes it look like nothing else

[Chorus]
He can't stop looking at her, he can't stop looking at her
She's talking about the Sounders and he forgot what words are for
He can't stop looking at her, he can't stop looking at her
Pretty Sara in the doorway of his fifteen thousand square foot store

[Verse 2]
Somebody brought a dog in and the whole room heard the squee
Sara on her knees in half a second, full of glee
The customers are startled but they're smiling ear to ear
And John's behind the counter thinking "God, I'm glad she's here"
Telly's waiting in the car, her little good boy in the seat
She'll be back to walk him down the length of Second Street

[Chorus]
He can't stop looking at her, he can't stop looking at her
She's got the ECS scarf on and her brother Kyle's on FaceTime from the war
He can't stop looking at her, he can't stop looking at her
Pretty Sara in the middle of his whole entire world

[Bridge]
She covers all the cool stuff happening around this town
But she doesn't even know she's the best thing he has found
Better than the Pioneer, better than the reel-to-reel
Fifteen thousand square feet and she's still the biggest deal
He's supposed to be working
He's supposed to be sorting
He's supposed to be something
But she walked in this morning

[Outro]
He can't stop looking at her
And he doesn't want to stop""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 28. Cloud 9 on Second Street — INDIE POP-ROCK
    # ------------------------------------------------------------------
    {
        "title": "Cloud 9 on Second Street",
        "genre_label": "INDIE POP-ROCK",
        "prompt": "Upbeat dreamy indie pop, shimmering guitars, sweet breathless female vocals, lovesick chorus, 126 BPM, summery and bright",
        "lyrics": """\
[Verse 1]
Saturday morning and the popcorn machine is on
Sara's at the counter with her laptop writing up what's going on
Weekend picks, the Scene section, deadline's almost here
But John just keeps refilling coffee she didn't ask for
Standing way too close, pretending he's straightening a shelf
She looks up and catches him and he can't help himself

[Pre-Chorus]
Every single time, every single time
She does that thing where she pushes back her hair
And he forgets that other people are standing there

[Chorus]
Cloud nine on Second Street, I swear he's floating
She said "the Sounders won" and his heart started going
Cloud nine on Second Street, the whole block knows it
John and Sara, they don't even try to hide it
Cloud nine, cloud nine

[Verse 2]
After close they're walking Telly past the barbershop
La Morenita's dark, the bakery light is off
Three Sisters' candles flickering through the window glass
She tells him about Kyle leading forty thousand people in a chant
He tells her about a Kenwood amp that came in beautiful today
She doesn't care about the amp but she loves the way he says it anyway

[Chorus]
Cloud nine on Second Street, I swear he's floating
She said "Kyle went crazy at the match" and his heart started going
Cloud nine on Second Street, the whole block knows it
John and Sara, they don't even try to hide it
Cloud nine, cloud nine

[Bridge]
A dog walked by the window and she squeeed so loud
Jerry dropped his joint next door and Carmen turned around
The whole block heard it, everybody smiled
That's just Sara, been that way a while
And John
John just stood there looking at her
Like she invented sunlight
Like she was the only record worth playing twice""",
        "status": "completed",
    },
    # ------------------------------------------------------------------
    # 29. Telly Knows — INDIE POP-ROCK
    # ------------------------------------------------------------------
    {
        "title": "Telly Knows",
        "genre_label": "INDIE POP-ROCK",
        "prompt": "Jangly indie pop-rock, playful bright guitars, cute female vocals, bouncy rhythm, 130 BPM, sweet and fun with heart",
        "lyrics": """\
[Verse 1]
Telly knows before she does when John is walking up the block
Little tail goes crazy and the whole leash starts to rock
Sara's on the phone with Kyle about the ECS tifo plan
But Telly's already pulling toward his favorite other man
John gets down and Telly licks his face from ear to chin
Sara says "He likes you more than me" with half a grin

[Chorus]
But the way he looks at her when she's not paying attention
The way he looks at her like she's the only thing worth mentioning
Telly knows, Telly knows
The little good boy always knows
He sees John watching Sara like she's everything that glows

[Verse 2]
Sunday afternoon they're in the Finds, she's got the laptop out
Scene section deadline, weekend picks, what Yak-eh-Mah's about
He's pretending to arrange the turntables in a line
But really he's just watching her type, thinking she's so fine
A customer walked in with a golden retriever pup
Sara hit a squee so high the reel-to-reels woke up

[Chorus]
But the way he looks at her when she's not paying attention
The way he looks at her like she's the only thing worth mentioning
Telly knows, Telly knows
The little good boy always knows
He sees John watching Sara like she's everything that glows

[Bridge]
She'll cover every show and every market on the scene
She'll scream for ninety minutes when the Sounders take the green
She'll squee at every dog from here to Tacoma and back
But she always ends up here, in the Finds, with the eight-tracks
And John will always be right there
Pretending not to stare
Sorting through the vinyl
Like he doesn't even care

[Outro]
But Telly knows
Oh, Telly knows
The tail don't lie
The little good boy's got the eye
John can't stop looking at her
And Telly thinks that's just fine""",
        "status": "completed",
    },
]
