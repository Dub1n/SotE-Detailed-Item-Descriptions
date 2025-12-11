
### Stamp (Upward Cut)

(Weapon Skill)
Weapon Damage: 2.1x [1x]
Stance Damage: 30-45 [5-8]

### War Cry

Stance Damage: 6
Heavy 1h (Roar Attack, Charged R2,)
    Weapon Damage: 1.4x, 1.4x | 1.8-1.9x, 1.8-2x
    Stance Damage: 8-15, 8-15 | 26-47, 25-46
Heavy 2h (Roar Attack, 2h Attack, Charged R2)
    Weapon Damage: 1.4-2x, 1.4-2x | 1.9-2.5x, 1.9-2.6x
    Stance Damage: 10-18, 10-18 | 31-52, 34-51

### Earthshaker

Hit (Weapon Skill)
    Weapon Damage: 1.6x [1.2x]
    Stance Damage9-12 [7-9]
Shockwave (Weapon Skill)
    Stance Damage: 30 [0]
    Physical Damage: 120 [85] [Strength]
Heavy Follow-up (Weapon Skill)
    Weapon Damage: 1.4x [1x]
    Stance Damage: 8-11 [6-8]

```md
### {Skill}

({subCategorySum})
if ({Follow-up} and {Hand} = "-") and ({Part} = "-")
{Text Wep Dmg}
{Text Wep Status}
{Text Stance}
{Text Phys}
{Text Mag}
{Text Fire}
{Text Ltng}
{Text Holy}

if ({Follow-up} and {Hand} = "-") and ({Part} =/= "-")
{Part} ({subCategorySum})
    {Text Wep Dmg}
    {Text Wep Status}
    {Text Stance}
    {Text Phys}
    {Text Mag}
    {Text Fire}
    {Text Ltng}
    {Text Holy}

if ({Follow-up} and/or {Hand} =/= "-") and ({Part} = "-")
{Follow-up} {Hand} ({subCategorySum})
    {Text Wep Dmg}
    {Text Wep Status}
    {Text Stance}
    {Text Phys}
    {Text Mag}
    {Text Fire}
    {Text Ltng}
    {Text Holy}

if ({Follow-up} and/or {Hand} =/= "-") and ({Part} =/= "-")
{Follow-up} {Hand}
    {Part} ({subCategorySum})
        {Text Wep Dmg}
        {Text Wep Status}
        {Text Stance}
        {Text Phys}
        {Text Mag}
        {Text Fire}
        {Text Ltng}
        {Text Holy}

where any {Text *} lines = "-" get excluded

For each skill that has more than one {Weapon} value:

### {Skill} 

#### {Weapon}

"

#### {Weapon}

"
...
```
