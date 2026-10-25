var CLOZE_IRREGULAR_GROUPS = [
  "be is are was were am been being", "get gets getting got gotten", "take takes taking took taken",
  "make makes making made", "give gives giving gave given", "come comes coming came",
  "go goes going went gone", "see sees seeing saw seen", "have has having had",
  "run runs running ran", "keep keeps keeping kept", "find finds finding found",
  "fall falls falling fell fallen", "break breaks breaking broke broken",
  "bring brings bringing brought", "buy buys buying bought", "catch catches catching caught",
  "choose chooses choosing chose chosen", "do does doing did done", "draw draws drawing drew drawn",
  "drive drives driving drove driven", "feel feels feeling felt", "fly flies flying flew flown",
  "grow grows growing grew grown", "hear hears hearing heard", "hold holds holding held",
  "know knows knowing knew known", "leave leaves leaving left", "lose loses losing lost",
  "pay pays paying paid", "put puts putting", "read reads reading", "say says saying said",
  "send sends sending sent", "show shows showing showed shown", "speak speaks speaking spoke spoken",
  "spend spends spending spent", "stand stands standing stood", "tell tells telling told",
  "think thinks thinking thought", "wear wears wearing wore worn", "win wins winning won",
  "write writes writing wrote written", "freeze freezes freezing froze frozen",
  "throw throws throwing threw thrown", "lend lends lending lent", "speed speeds speeding sped",
  "swear swears swearing swore sworn", "bite bites biting bit bitten", "hide hides hiding hid hidden",
  "wake wakes waking woke woken", "strike strikes striking struck", "steal steals stealing stole stolen",
  "shake shakes shaking shook shaken", "blow blows blowing blew blown",
  "forget forgets forgetting forgot forgotten", "forgive forgives forgiving forgave forgiven",
  "tear tears tearing tore torn", "bear bears bearing bore born borne", "ride rides riding rode ridden",
  "rise rises rising rose risen", "arise arises arising arose arisen", "sink sinks sinking sank sunk",
  "shrink shrinks shrinking shrank shrunk", "spin spins spinning spun", "swing swings swinging swung",
  "bind binds binding bound", "feed feeds feeding fed", "flee flees fleeing fled",
  "sweep sweeps sweeping swept", "stick sticks sticking stuck", "dig digs digging dug",
  "bleed bleeds bleeding bled", "breed breeds breeding bred", "kneel kneels kneeling knelt",
  "creep creeps creeping crept", "weep weeps weeping wept", "cling clings clinging clung",
  "fling flings flinging flung", "sting stings stinging stung", "string strings stringing strung",
  "wring wrings wringing wrung", "spit spits spitting spat", "spill spills spilling spilt spilled",
  "leap leaps leaping leapt leaped", "bid bids bidding", "forbid forbids forbidding forbade forbidden",
  "undergo undergoes undergoing underwent undergone", "undertake undertakes undertaking undertook undertaken",
  "overcome overcomes overcoming overcame", "withdraw withdraws withdrawing withdrew withdrawn",
  "withhold withholds withholding withheld", "uphold upholds upholding upheld",
  "lay lays laying laid", "lie lies lying lay lain", "set sets setting", "cut cuts cutting",
  "let lets letting", "hit hits hitting", "sit sits sitting sat", "meet meets meeting met",
  "lead leads leading led", "build builds building built", "begin begins beginning began begun",
  "seek seeks seeking sought", "sell sells selling sold", "teach teaches teaching taught",
  "become becomes becoming became", "mean means meaning meant", "hang hangs hanging hung",
  "shoot shoots shooting shot", "shut shuts shutting", "sing sings singing sang sung",
  "swim swims swimming swam swum", "drink drinks drinking drank drunk", "eat eats eating ate eaten",
  "lend lends lending lent", "rid rids ridding", "slide slides sliding slid", "split splits splitting",
  "spread spreads spreading", "thrust thrusts thrusting", "burst bursts bursting", "cast casts casting",
  "cost costs costing", "deal deals dealing dealt", "dream dreams dreaming dreamt dreamed",
  "light lights lighting lit lighted", "mistake mistakes mistaking mistook mistaken",
  "overtake overtakes overtaking overtook overtaken", "prove proves proving proved proven",
  "quit quits quitting", "shed sheds shedding", "slay slays slaying slew slain", "sow sows sowing sowed sown",
  "stride strides striding strode stridden", "sweat sweats sweating", "tread treads treading trod trodden",
  "understand understands understanding understood", "wind winds winding wound"
];
var CLOZE_IRREGULARS = {};
CLOZE_IRREGULAR_GROUPS.forEach(function (g) {
  var forms = g.split(" ");
  var pat = "(?:" + forms.join("|") + ")";
  forms.forEach(function (f) {
    if (!CLOZE_IRREGULARS[f]) CLOZE_IRREGULARS[f] = pat;
  });
});
