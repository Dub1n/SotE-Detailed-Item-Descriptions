# Weapon Art Damage Guide

Huge thanks to sleepless\_sheeple for a lot of the theory in this guide. Most of the conclusions and formulas here are their work, I’m just presenting them.

## Key Takeaways (tl;dr;)

If you are only going to read one section, read this. There are three categories of weapon arts.

Values for all skills is in the "Ash of War Attack Data" tab of this spreadsheet: [ER - Motion Values and Attack Data (App Ver. 1.04.1)](https://docs.google.com/spreadsheets/d/1j4bpTbsnp5Xsgw9TP2xv6d8R4qk0ErpE9r_5LGIDraU/edit#gid=362983777)

Arts that hit with your weapon (aka "**Weapon**" Hits) depend on your weapon’s AR. Simple.

Arts that hit with anything other than your weapon (aka "**Bullet**") depend **only** on:

* weapon upgrade level
* 1-2 of your stats decided by the affinity of the Art (eg Dex for Keen Art, Int \+ Dex for Cold)  
* the affinity of your weapon, **not the actual scaling on your weapon. Just the affinity**  
* Calculator for Bullet art damage: [Bullet Weapon Art Damage Calculator (v1.0)](https://docs.google.com/spreadsheets/d/1X3LNB8lFqwcCFyFckE7Pd2dgdsHbAf5RS0znkMieWp0/copy?usp=sharing)

It’s possible to have an "**Enhanced**" hit that hits with your weapon while it’s magically enhanced. These work like a combination of the other two types: you simultaneously get a MV times your weapon’s base attack, and a bullet-like component with base\_damage as well.

Weapon upgrade level is incredibly important to Bullet or Enhanced-type Arts’ damage. At max level, the base damage of the art is x4, and the scaling for your stats is also better.

The affinity of the weapon you’re using affects damage of Bullet-type Arts in two ways:

* Gives a stat multiplier to the effect of your stats. Try to use an affinity that boosts the stat your Art cares about  
* Changes the stat curve used to find the effectiveness of your stats. Using an elemental affinity causes it to use the elemental stat curve, which is more efficient. This can lead to a big damage difference at low-medium stat levels

While you can boost the damage of Bullet-type arts by choosing an affinity that focuses on the same stats that the Art uses, the scaling from stats is much smaller than the stat scaling on weapons. Base damage is most important. Even at max stats, you’re only going to get about a 50-60% damage increase over no stats at all.

## Types of Hit

There's a fundamental split between three types of hits from Skills:

1. those that hit with the actual weapon  
2. those that hit with a buffed version of your weapon  
3. those that instead hit with a projectile or something other than your normal weapon.

I will be calling these **Weapon Hits, Enhanced Hits,** and **Bullet Hits**, though not all are projectiles / bullets. Bullet is a term taken from the game files.

Some weapon skills have multiple hits that may be different types: eg Gravitas has an initial Enhanced Hit when you thrust your weapon into the ground, and then a Bullet Hit when you pull enemies towards you. The scaling behaviour for each type of hit is completely different.

### Type 1: Weapon Hits

Anything that hits with your physical weapon. A few examples:

* Sword Dance  
* Unsheathe  
* Giant Hunt

#### Weapon Hits: Damage Model

The simpler of the two types. Damage model is just:

* damage \= weapon\_ar x motion\_value

Where motion\_value is based on the specific weapon art. It’s just a hard-hitting normal attack

### Type 2: Enhanced Hits

Anything that attacks with an enhanced or magically buffed weapon. Examples:

* Loretta’s Slash  
* Glintstone Pebble (2nd hit)  
* Flaming Strike (2nd hit)

These are mostly the same as Weapon Hits, just an attack with your weapon’s AR and a Motion Value, but the attack gives your weapon a very short-lived non-physical attack buff just for the duration of the move.

The strength of that buff scales with a specific stat, and uses your weapon’s scaling modifier for that stat.These buffs *will* stack with existing buffs on your weapon, such as Greases or weapon buff spells, even ones with different damage types.

Eg Loretta’s Slash gives a Magic buff that scales with Int, and uses your weapon’s actual Int scaling for that buff. If your weapon has no Int scaling, you will just get the base buff with no stat bonus.

#### Enahnced Hits: Damage Model

Normal weapon hit with a high motion value, \+ a temporary buff on your weapon for the duration of the hit. The weapon buff has a separate Motion Value that is always 100\.

* buff\_strength \= base\_buff \* (1 \+ 3 \* pct\_upgraded) \* (1 \+ sum of each stat\_bonus)  
* stat\_bonus \= weapon\_scaling\_multiplier \* stat\_multiplier

where

* base\_buff \= base buff amount of the weapon art  
* pct\_upgraded \= current upgrade level/max upgrade level. So at max upgrade level, the base buff amount is 4x  
* weapon\_scaling\_multiplier \= the scaling of your weapon for the relevant stat. Just the scaling letter visible on your equipment screen. Improves with upgrades  
* stat\_multiplier \= multiplier based on stat investment. Same calculation used for Weapon AR: it’s the stat curve that we use to find Soft caps, etc

So upgrading your weapon affects the formula in two ways: the base buff goes up to 4x directly with weapon upgrade level, and the weapon\_scaling\_multiplier also improves as your weapon is upgraded.

Note: for those who don’t already know, Weapon Buffs of all kinds aren’t affected by attack Motion Values. They have their own set of Weapon Buff MVs, which are 100 (default) for almost all attacks. So a charged heavy will do the same amount of bonus damage from buffs as a fast light. [Weapon Buff MVs can be found here](https://docs.google.com/spreadsheets/d/1j4bpTbsnp5Xsgw9TP2xv6d8R4qk0ErpE9r_5LGIDraU/edit?usp=sharing).

### Type 3: Bullet Hits

Anything that hits with something other than your actual weapon. Eg rolling at an enemy, throwing a projectile of some sort, attacking with a blood blade, etc. A few examples:

* Beast Roar  
* Glintstone Pebble (1st hit)  
* Thunderbolt  
* Lightning Ram  
* Sacred Blade  
* Bloody Slash  
* Hoarfrost Stomp

These *completely ignore your weapon’s AR and scaling*. For the most part, the specific weapon you use for them does not matter. There are only 3 things that affect their damage:

* Your weapon’s Upgrade Level  
* 1 or 2 stats, depending on affinity the Weapon Art belongs to (see chart below)  
* Your weapon’s Affinity, which multiplies your stat scaling

Unlike Enhanced Hits, the specific weapon you’re using mostly *does not matter* for Bullet Arts. Only the affinity matters. A Fire Dagger \+25 and a Fire Greatsword \+25 will do *exactly* the same damage for a Str Art, even though the Greatsword scales better with Strength and has much more AR.

There’s one exception to this: Heavy and Keen affinity. And it’s the opposite of what you would expect.

You get a worse Str multiplier for Heavy if it’s on a weapon that already scaled well with Str, than if your weapon was not Str-focused. Eg if the Dagger and Greatsword were both Heavy instead of Fire, the Dagger would actually do **more damage** than the Greatsword, because the Greatsword is already considered a Str-focused weapon.

Same logic with Keen, it’s worse on Dex-focused weapons. There’s a full list of all weapons that are worse with Heavy or worse with Keen in the "Relevant Stats for Bullet Hits" section later.

#### Bullet Hits: Damage Model

Current model for "bullet" Weapon Art damage pre-defence and absorption is:

* damage \= base\_damage \* (1 \+ 3 \* pct\_upgraded) \* (1 \+ sum of each stat\_bonus )  
* stat\_bonus \= base\_scaling \* affinity\_scaling\_multiplier \* stat\_multiplier

where

* base\_damage \= base damage of the weapon art  
* pct\_upgraded \= current upgrade level/max upgrade level. So at max upgrade level, the base damage is 4x  
* base\_scaling \= scaling at no upgrade for a particular stat. Depends on Bullet Art affinity:  
  * For Bullet Arts that only depend on a single stat \= 0.25  
  * For Cold or Quality Bullet Arts, which depend on two stats \= 0.15  
  * For Unique weapon arts \= same as the scaling on the weapon  
* affinity\_scaling\_multiplier \= multiplier based on a given stat, **weapon level**, and **affinity**  
  * See chart below for these numbers. These increase as your weapon is upgraded. These are mostly the same across all Magic weapons, all Quality weapons, etc. Specific weapon doesn’t matter  
* stat\_multiplier \= multiplier based on stat investment (same stat curve used for weapon scaling). The affinity you choose for your weapon can affect this, since Str, Dex and Arc have different stat saturation curves for Standard vs Heavy vs Quality etc

##### Example

For example, let’s say I’m using a Sacred Bullet Art with a **base\_damage** of 100\.

My weapon is \+25, so my **pct\_upgraded** is 25/25 \= 1\.

**base\_scaling** for all infusible weapon arts is 0.25.

I have 80 Faith, which by checking the [Scaling Data Sheet](https://docs.google.com/spreadsheets/d/1zoJIRmr-00XC1Rd-SwIpeNoHNpehY2kRHoh-4WeACxc/edit#gid=476811623), I can see that gives me 0.90 of my possible extra damage from Faith. This is my **stat\_multiplier**.

The Faith **affinity\_scaling\_multiplier** on a fully upgraded, Standard-affinity weapon is 1.8. **It does not matter what the weapon is\!** The scaling\_multiplier is entirely based on the Affinity and upgrade level, and will be the same for *all* weapons with that affinity. A Fire Dagger will do the same Bullet Art damage as a Fire Greatsword.

Putting this all together:

* stat\_bonus \= 0.25 \* 1.8 \* 0.90 \= **0.405**  
* damage \= 100 \* (1 \+ 3 \* 25/25) \* (1 \+ 0.405)  
  * \= 400 \* 1.405  
  * \= **562**

### Relevant Stats for Bullet Hits

Bullet Hits only care about specific stats, and ignore all others.

This is based on what affinity type the Weapon Art belongs to. It doesn’t matter what actual affinity your weapon actually has at this stage: a Keen Art like Beast Roar will always only scale with Dex, even when on a Heavy or Magic weapon

Each affinity class only cares about the particular primary stat it would use as a weapon infusion.

| Weapon Art Affinity | Relevant Stat |
| :------------------ | :------------ |
| Heavy               | STR           |
| Keen                | DEX           |
| Quality             | STR \+ DEX    |
| Magic               | INT           |
| Fire                | STR           |
| Lightning           | DEX           |
| Flame               | FTH           |
| Sacred              | FTH           |
| Poison              | ARC           |
| Blood               | ARC           |
| Cold                | INT \+ DEX    |
| Occult              | ARC           |

#### Which Affinity is best for Bullet Hits?

Calculator to do the maths for you: [Bullet Art Calculator (v1.0)](https://docs.google.com/spreadsheets/d/1YEMklcpxQjR5BW0AFwxPkMi0XX2CvJgZsj53I5H8N1U/copy?usp=sharing)

**Elemental vs Physical Stat Curve**  
![][image1]  
If you’re using a Bullet art that does Elemental damage, then using a matching weapon affinity (eg Magic or Cold affinity for Magic damage, or Fire or Flame Art affinity for Fire damage) then your stats will use the more efficient Elemental Stat Curve \#4, the red line above. Using the wrong element affinity (eg Heavy, Poison) gives you the default, less efficient Curve \#0 instead.

So does this mean you should always use Fire weapon affinity for a Fire Bullet art, for the better stat curve? Not necessarily.

Heavy has a stronger Strength affinity\_scaling\_multiplier than Fire. So at high amounts of Strength, Heavy will be better than Fire. Where is this breakpoint? At about 25 in a stat.  
![][image2]  
After about 25 in your damage Stat, Heavy will be better than Fire for Fire bullet arts. And Keen will be better than Lightning for Lightning bullet arts.

### Chart of affinity\_scaling\_multiplier by Affinity (at max upgrade level)

Each affinity has a multiplier for your stat scaling. Eg if you have \+15% damage from Strength with a Standard affinity, you would have \+28% bonus damage with a Heavy affinity, ignoring differences in stat curve

| Affinity | Str | Dex | Int | Fai | Arc |
| :---- | ----- | ----- | ----- | ----- | ----- |
| Standard | 1.5 | 1.5 | 1.8 | 1.8 | 1.8 |
| Heavy (most weps) | 2.8 | 0 | 1.8 | 1.8 | 1.8 |
| Heavy (Str-focused weps) | 2.6 | 1.2 | 1.8 | 1.8 | 1.8 |
| Keen (most weps) | 1.3 | 2.8 | 1.8 | 1.8 | 1.8 |
| Keen (Dex-focused weps) | 1.3 | 2.5 | 1.8 | 1.8 | 1.8 |
| Quality | 1.9 | 1.9 | 1.8 | 1.8 | 1.8 |
| Fire | 2.1 | 1.2 | 1.8 | 1.8 | 1.8 |
| Flame Art | 1.8 | 1.8 | 1.8 | 2.3 | 1.8 |
| Lightning | 1.2 | 2.1 | 1.8 | 1.8 | 1.8 |
| Sacred | 1.8 | 1.8 | 1.8 | 2.3 | 1.8 |
| Magic | 1.3 | 1.3 | 2.35 | 1.8 | 1.8 |
| Cold | 1.9 | 1.9 | 2 | 1.8 | 1.8 |
| Poison | 1.9 | 1.9 | 1.9 | 1.9 | 1.45 |
| Blood | 1.9 | 1.9 | 1.9 | 1.9 | 1.45 |
| Occult | 1.5 | 1.5 | 1.5 | 1.5 | 1.8 |

Here's an image of the full set of multipliers, including those for unique weapons or those which can't have weapon arts at all: [https://imgur.com/a/6YCLveP](https://imgur.com/a/6YCLveP)

There are a few oddities in the affinity\_scaling\_multipliers.

* There are two types of Heavy, and two types of Keen. Applying Heavy to a weapon that already scales well with Strength, or Keen to a weapon that already scales well with Dex, has a lower scaling\_multiplier than using an unsuitable weapon for some reason. So if you want to maximize your Thunderbolt damage, put it on a Keen Greatsword, not a Keen Dagger  
* Putting Lightning or Keen bullet-type Arts on most Heavy weapons is a bad idea. Those Arts scale with Dex, and Heavy’s Dex multiplier is 0\. So even with your 99 Dex, your stat bonus will be 0\. That means the only part of the formula that matters is your base damage and upgrade level, and your damage will never get any higher. You’re limited to 4x the unupgraded base damage  
* Poison and Blood have bad Arcane scaling. Your Poison, Blood, or Occult "bullet"-type Arts all scale with Arcane, so will do more damage on literally any affinity other than Poison or Blood  
* Similarly, Occult affinity nerfs the scaling for all stats other than Arcane

#### List of those weapons that have worse Heavy / Keen scaling

Weapons with a worse Str scaling on Bullet Hits when Heavy:  
Heavy Bloodstained Dagger, Heavy Broadsword, Heavy Bastard Sword, Heavy Iron Greatsword, Gargoyle's Heavy Greatsword, Heavy Greatsword, Watchdog's Heavy Greatsword, Beastman's Heavy Curved Sword, Serpent-God's Heavy Curved Sword, Beastman's Heavy Cleaver, Gargoyle's Heavy Twinblade, Heavy Curved Club, Heavy Hammer, Heavy Stone Club, Heavy Large Club, Heavy Battle Hammer, Heavy Great Mace, Heavy Pickaxe, Heavy Brick Hammer, Heavy Rotten Battle Hammer, Heavy Chainlink Flail, Heavy Jawbone Axe, Heavy Iron Cleaver, Heavy Warped Axe, Heavy Rusted Anchor, Executioner's Heavy Greataxe, Gargoyle's Heavy Great Axe, Clayman's Heavy Harpoon, Heavy Nightrider Glaive, Gargoyle's Heavy Halberd, Heavy Iron Ball, Heavy Star Fist, Prelate's Heavy Inferno Crozier, Heavy Great Club, Heavy Giant-Crusher, Golem's Heavy Halberd

Weapons with a worse Dex scaling on Bullet Hits when Keen:

Keen Dagger, Keen Parrying Dagger, Keen Misericorde, Celebrant's Keen Sickle, Keen Great Knife, Keen Shortsword, Keen Cane Sword, Noble's Keen Slender Sword, Warhawk's Keen Talon, Keen Flamberge, Keen Estoc, Keen Rapier, Rogier's Keen Rapier, Keen Shotel, Flowing Keen Curved Sword, Keen Scimitar, Keen Nagakiba, Keen Godskin Peeler, Monk's Keen Flamemace, Keen Nightrider Flail, Keen Forked Hatchet, Keen Butchering Knife, Keen Spear, Celebrant's Keen Rib-Rake, Keen Cross-Naginata, Keen Lucerne, Keen Vulgar Militia Shotel, Keen Scythe, Keen Thorned Whip, Keen Hookclaws, Keen Raptor Talons, Keen Duelist Greataxe, Keen Rotten Greataxe

### Worked Bullet Hit Example

Your weapon’s affinity has a large effect on the damage your Bullet hits do. It both changes your affinity\_scaling\_multiplier, and changes the stat curve your weapon uses for that element.

As a reminder:

* damage \= base\_damage \* (1 \+ 3 \* pct\_upgraded) \* (1 \+ sum of each stat\_bonus )  
* stat\_bonus \= base\_scaling \* affinity\_scaling\_multiplier \* stat\_multiplier

And from our worked example with a Standard affinity weapon:

* stat\_bonus \= 0.25 \* 1.8 \* 0.90 \= **0.405**  
* damage \= 100 \* (1 \+ 3 \* 25/25) \* (1 \+ 0.405)  
  * \= 400 \* 1.405  
  * \= **562**

By changing from Standard to a Flame Art affinity, I improve my damage in two ways

1. Changed my affinity\_scaling\_multiplier for Faith from 1.8 to 2.3, as Flame Art is better for Faith  
2. Changed the stat curve I’m using. Flame Art uses the more efficient elemental damage stat curve (\#4) for Fire damage, so at 80 Faith my stat\_multiplier is 0.95 instead of 0.90

As a result, my stat\_bonus will be higher, and so my final damage will be higher also.

* stat\_bonus \= 0.25 \* **2.3** \* **0.95** \= **0.54625**  
* damage \= 100 \* (1 \+ 3 \* 25/25) \* (1 \+ 0.54625)  
  * \= 400 \* 1.54625  
  * \= **618.5**

## Evidence, References

Again, huge thanks to sleepless\_sheeple. They found most of the damage models, and without them this document wouldn’t exist.

Here's a spreadsheet with my recorded numbers when first testing weapon arts: [https://docs.google.com/spreadsheets/d/e/2PACX-1vR5lvYuKSMsnvQbSierAiYWP6wGdyyT9ey61GoEFVow5iV-tpXPU\_ATkkjOspFkUY6pCnkXsmV0ZzoT/pubhtml](https://docs.google.com/spreadsheets/d/e/2PACX-1vR5lvYuKSMsnvQbSierAiYWP6wGdyyT9ey61GoEFVow5iV-tpXPU_ATkkjOspFkUY6pCnkXsmV0ZzoT/pubhtml)

My base stats are Level 102, with 45 Vigor, 15 Mind, 20 Endurance, 28 Strength, 48 Dexterity, 15 Intelligence, 35 Faith and 15 Arcane (I had \+5 Great Rune active while testing).

My methodology was to hit the troll outside of Godrick's boss arena with a \+12 Godskin Peeler, so I didn't kill it too fast. Then to swap on the \+5 stat artifacts to see how stats changing affected the Skill damage, or the Albinauric Mask for ARC. Any cells that don't have a value I didn't test, since they didn't seem relevant. Stuff like \+5 FTH on a Magic affinity skill.

Spreadsheet with all the different scaling\_multipliers, even those for weapons that cannot have Arts: [https://docs.google.com/spreadsheets/d/1LUVbSufvocMb8rutaAkMDU\_hxaU1wGsi-sny5NHsuE8/edit?usp=sharing](https://docs.google.com/spreadsheets/d/1LUVbSufvocMb8rutaAkMDU_hxaU1wGsi-sny5NHsuE8/edit?usp=sharing)

This was calculated by opening the [Elden Ring Weapon Data Sheet](https://docs.google.com/spreadsheets/d/1k8Qq8X2XzZ6gY2wsibQPCOvn2VE0d9czlmAam8DWYIA/edit#gid=670105415), and looking at the Scaling\_Upgrades tab for the Reinforce Type ID for each weapon. Then in ReinforceParamWeapon look up the stat scaling for [that ID (ranges from ID to ID+max upgrade level) and the stat in question.](https://i.imgur.com/KVfS5Gm.png)

Calculator for Bullet weapon Art damage: [Bullet Art Calculator (v1.0)](https://docs.google.com/spreadsheets/d/1YEMklcpxQjR5BW0AFwxPkMi0XX2CvJgZsj53I5H8N1U/copy?usp=sharing)
