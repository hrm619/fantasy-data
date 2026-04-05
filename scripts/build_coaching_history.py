"""Build coaching_staff JSON files for 2014-2023 seasons.

HC and OC assignments sourced from Pro Football Reference coaching records.
Continuity flags computed automatically: if HC/OC name matches the previous
season for the same team, continuity=1 and year increments.

System tags are assigned based on coaching tree lineage.

Usage:
    uv run python scripts/build_coaching_history.py
"""

import json
from pathlib import Path

# HC and OC by team and season (2014-2023)
# Format: {team: {season: (hc, oc)}}
# Sources: PFR coaching records, team press releases

COACHING_DATA: dict[str, dict[int, tuple[str, str]]] = {
    "ARI": {
        2014: ("Bruce Arians", "Harold Goodwin"),
        2015: ("Bruce Arians", "Harold Goodwin"),
        2016: ("Bruce Arians", "Harold Goodwin"),
        2017: ("Bruce Arians", "Harold Goodwin"),
        2018: ("Steve Wilks", "Mike McCoy"),
        2019: ("Kliff Kingsbury", "Kliff Kingsbury"),
        2020: ("Kliff Kingsbury", "Kliff Kingsbury"),
        2021: ("Kliff Kingsbury", "Kliff Kingsbury"),
        2022: ("Kliff Kingsbury", "Kliff Kingsbury"),
        2023: ("Jonathan Gannon", "Drew Petzing"),
    },
    "ATL": {
        2014: ("Mike Smith", "Dirk Koetter"),
        2015: ("Dan Quinn", "Kyle Shanahan"),
        2016: ("Dan Quinn", "Kyle Shanahan"),
        2017: ("Dan Quinn", "Steve Sarkisian"),
        2018: ("Dan Quinn", "Steve Sarkisian"),
        2019: ("Dan Quinn", "Dirk Koetter"),
        2020: ("Raheem Morris", "Dirk Koetter"),
        2021: ("Arthur Smith", "Dave Ragone"),
        2022: ("Arthur Smith", "Dave Ragone"),
        2023: ("Arthur Smith", "Dave Ragone"),
    },
    "BAL": {
        2014: ("John Harbaugh", "Gary Kubiak"),
        2015: ("John Harbaugh", "Marc Trestman"),
        2016: ("John Harbaugh", "Marty Mornhinweg"),
        2017: ("John Harbaugh", "Marty Mornhinweg"),
        2018: ("John Harbaugh", "Marty Mornhinweg"),
        2019: ("John Harbaugh", "Greg Roman"),
        2020: ("John Harbaugh", "Greg Roman"),
        2021: ("John Harbaugh", "Greg Roman"),
        2022: ("John Harbaugh", "Greg Roman"),
        2023: ("John Harbaugh", "Todd Monken"),
    },
    "BUF": {
        2014: ("Doug Marrone", "Nathaniel Hackett"),
        2015: ("Rex Ryan", "Greg Roman"),
        2016: ("Rex Ryan", "Anthony Lynn"),
        2017: ("Sean McDermott", "Rick Dennison"),
        2018: ("Sean McDermott", "Brian Daboll"),
        2019: ("Sean McDermott", "Brian Daboll"),
        2020: ("Sean McDermott", "Brian Daboll"),
        2021: ("Sean McDermott", "Brian Daboll"),
        2022: ("Sean McDermott", "Ken Dorsey"),
        2023: ("Sean McDermott", "Joe Brady"),
    },
    "CAR": {
        2014: ("Ron Rivera", "Mike Shula"),
        2015: ("Ron Rivera", "Mike Shula"),
        2016: ("Ron Rivera", "Mike Shula"),
        2017: ("Ron Rivera", "Mike Shula"),
        2018: ("Ron Rivera", "Norv Turner"),
        2019: ("Ron Rivera", "Norv Turner"),
        2020: ("Matt Rhule", "Joe Brady"),
        2021: ("Matt Rhule", "Joe Brady"),
        2022: ("Matt Rhule", "Ben McAdoo"),
        2023: ("Frank Reich", "Thomas Brown"),
    },
    "CHI": {
        2014: ("Marc Trestman", "Aaron Kromer"),
        2015: ("John Fox", "Adam Gase"),
        2016: ("John Fox", "Dowell Loggains"),
        2017: ("John Fox", "Dowell Loggains"),
        2018: ("Matt Nagy", "Mark Helfrich"),
        2019: ("Matt Nagy", "Mark Helfrich"),
        2020: ("Matt Nagy", "Bill Lazor"),
        2021: ("Matt Nagy", "Bill Lazor"),
        2022: ("Matt Eberflus", "Luke Getsy"),
        2023: ("Matt Eberflus", "Luke Getsy"),
    },
    "CIN": {
        2014: ("Marvin Lewis", "Hue Jackson"),
        2015: ("Marvin Lewis", "Hue Jackson"),
        2016: ("Marvin Lewis", "Ken Zampese"),
        2017: ("Marvin Lewis", "Bill Lazor"),
        2018: ("Marvin Lewis", "Bill Lazor"),
        2019: ("Zac Taylor", "Brian Callahan"),
        2020: ("Zac Taylor", "Brian Callahan"),
        2021: ("Zac Taylor", "Brian Callahan"),
        2022: ("Zac Taylor", "Brian Callahan"),
        2023: ("Zac Taylor", "Brian Callahan"),
    },
    "CLE": {
        2014: ("Mike Pettine", "Kyle Shanahan"),
        2015: ("Mike Pettine", "John DeFilippo"),
        2016: ("Hue Jackson", "Hue Jackson"),
        2017: ("Hue Jackson", "Todd Haley"),
        2018: ("Hue Jackson", "Todd Haley"),
        2019: ("Freddie Kitchens", "Todd Monken"),
        2020: ("Kevin Stefanski", "Alex Van Pelt"),
        2021: ("Kevin Stefanski", "Alex Van Pelt"),
        2022: ("Kevin Stefanski", "Alex Van Pelt"),
        2023: ("Kevin Stefanski", "Alex Van Pelt"),
    },
    "DAL": {
        2014: ("Jason Garrett", "Scott Linehan"),
        2015: ("Jason Garrett", "Scott Linehan"),
        2016: ("Jason Garrett", "Scott Linehan"),
        2017: ("Jason Garrett", "Scott Linehan"),
        2018: ("Jason Garrett", "Scott Linehan"),
        2019: ("Jason Garrett", "Kellen Moore"),
        2020: ("Mike McCarthy", "Kellen Moore"),
        2021: ("Mike McCarthy", "Kellen Moore"),
        2022: ("Mike McCarthy", "Kellen Moore"),
        2023: ("Mike McCarthy", "Brian Schottenheimer"),
    },
    "DEN": {
        2014: ("John Fox", "Adam Gase"),
        2015: ("Gary Kubiak", "Rick Dennison"),
        2016: ("Gary Kubiak", "Rick Dennison"),
        2017: ("Vance Joseph", "Mike McCoy"),
        2018: ("Vance Joseph", "Bill Musgrave"),
        2019: ("Vic Fangio", "Rich Scangarello"),
        2020: ("Vic Fangio", "Pat Shurmur"),
        2021: ("Vic Fangio", "Pat Shurmur"),
        2022: ("Nathaniel Hackett", "Justin Outten"),
        2023: ("Sean Payton", "Joe Lombardi"),
    },
    "DET": {
        2014: ("Jim Caldwell", "Joe Lombardi"),
        2015: ("Jim Caldwell", "Jim Bob Cooter"),
        2016: ("Jim Caldwell", "Jim Bob Cooter"),
        2017: ("Jim Caldwell", "Jim Bob Cooter"),
        2018: ("Matt Patricia", "Jim Bob Cooter"),
        2019: ("Matt Patricia", "Darrell Bevell"),
        2020: ("Matt Patricia", "Darrell Bevell"),
        2021: ("Dan Campbell", "Anthony Lynn"),
        2022: ("Dan Campbell", "Ben Johnson"),
        2023: ("Dan Campbell", "Ben Johnson"),
    },
    "GB": {
        2014: ("Mike McCarthy", "Tom Clements"),
        2015: ("Mike McCarthy", "Edgar Bennett"),
        2016: ("Mike McCarthy", "Edgar Bennett"),
        2017: ("Mike McCarthy", "Edgar Bennett"),
        2018: ("Mike McCarthy", "Joe Philbin"),
        2019: ("Matt LaFleur", "Nathaniel Hackett"),
        2020: ("Matt LaFleur", "Nathaniel Hackett"),
        2021: ("Matt LaFleur", "Nathaniel Hackett"),
        2022: ("Matt LaFleur", "Adam Stenavich"),
        2023: ("Matt LaFleur", "Adam Stenavich"),
    },
    "HOU": {
        2014: ("Bill O'Brien", "Bill O'Brien"),
        2015: ("Bill O'Brien", "George Godsey"),
        2016: ("Bill O'Brien", "George Godsey"),
        2017: ("Bill O'Brien", "Bill O'Brien"),
        2018: ("Bill O'Brien", "Bill O'Brien"),
        2019: ("Bill O'Brien", "Tim Kelly"),
        2020: ("Bill O'Brien", "Tim Kelly"),
        2021: ("David Culley", "Tim Kelly"),
        2022: ("Lovie Smith", "Pep Hamilton"),
        2023: ("DeMeco Ryans", "Bobby Slowik"),
    },
    "IND": {
        2014: ("Chuck Pagano", "Pep Hamilton"),
        2015: ("Chuck Pagano", "Pep Hamilton"),
        2016: ("Chuck Pagano", "Rob Chudzinski"),
        2017: ("Chuck Pagano", "Rob Chudzinski"),
        2018: ("Frank Reich", "Nick Sirianni"),
        2019: ("Frank Reich", "Nick Sirianni"),
        2020: ("Frank Reich", "Nick Sirianni"),
        2021: ("Frank Reich", "Marcus Brady"),
        2022: ("Frank Reich", "Marcus Brady"),
        2023: ("Shane Steichen", "Jim Bob Cooter"),
    },
    "JAX": {
        2014: ("Gus Bradley", "Jedd Fisch"),
        2015: ("Gus Bradley", "Greg Olson"),
        2016: ("Gus Bradley", "Greg Olson"),
        2017: ("Doug Marrone", "Nathaniel Hackett"),
        2018: ("Doug Marrone", "John DeFilippo"),
        2019: ("Doug Marrone", "John DeFilippo"),
        2020: ("Doug Marrone", "Jay Gruden"),
        2021: ("Urban Meyer", "Darrell Bevell"),
        2022: ("Doug Pederson", "Press Taylor"),
        2023: ("Doug Pederson", "Press Taylor"),
    },
    "KC": {
        2014: ("Andy Reid", "Doug Pederson"),
        2015: ("Andy Reid", "Doug Pederson"),
        2016: ("Andy Reid", "Matt Nagy"),
        2017: ("Andy Reid", "Matt Nagy"),
        2018: ("Andy Reid", "Eric Bieniemy"),
        2019: ("Andy Reid", "Eric Bieniemy"),
        2020: ("Andy Reid", "Eric Bieniemy"),
        2021: ("Andy Reid", "Eric Bieniemy"),
        2022: ("Andy Reid", "Eric Bieniemy"),
        2023: ("Andy Reid", "Matt Nagy"),
    },
    "LAC": {
        2014: ("Mike McCoy", "Frank Reich"),
        2015: ("Mike McCoy", "Frank Reich"),
        2016: ("Mike McCoy", "Ken Whisenhunt"),
        2017: ("Anthony Lynn", "Ken Whisenhunt"),
        2018: ("Anthony Lynn", "Ken Whisenhunt"),
        2019: ("Anthony Lynn", "Shane Steichen"),
        2020: ("Anthony Lynn", "Shane Steichen"),
        2021: ("Brandon Staley", "Joe Lombardi"),
        2022: ("Brandon Staley", "Joe Lombardi"),
        2023: ("Brandon Staley", "Kellen Moore"),
    },
    "LAR": {
        2014: ("Jeff Fisher", "Brian Schottenheimer"),
        2015: ("Jeff Fisher", "Frank Cignetti"),
        2016: ("Jeff Fisher", "Rob Boras"),
        2017: ("Sean McVay", "Matt LaFleur"),
        2018: ("Sean McVay", "Sean McVay"),
        2019: ("Sean McVay", "Sean McVay"),
        2020: ("Sean McVay", "Kevin O'Connell"),
        2021: ("Sean McVay", "Kevin O'Connell"),
        2022: ("Sean McVay", "Liam Coen"),
        2023: ("Sean McVay", "Mike LaFleur"),
    },
    "LV": {
        2014: ("Dennis Allen", "Greg Olson"),
        2015: ("Jack Del Rio", "Bill Musgrave"),
        2016: ("Jack Del Rio", "Bill Musgrave"),
        2017: ("Jack Del Rio", "Todd Downing"),
        2018: ("Jon Gruden", "Jon Gruden"),
        2019: ("Jon Gruden", "Jon Gruden"),
        2020: ("Jon Gruden", "Greg Olson"),
        2021: ("Jon Gruden", "Greg Olson"),
        2022: ("Josh McDaniels", "Mick Lombardi"),
        2023: ("Josh McDaniels", "Mick Lombardi"),
    },
    "MIA": {
        2014: ("Joe Philbin", "Bill Lazor"),
        2015: ("Joe Philbin", "Bill Lazor"),
        2016: ("Adam Gase", "Clyde Christensen"),
        2017: ("Adam Gase", "Clyde Christensen"),
        2018: ("Adam Gase", "Dowell Loggains"),
        2019: ("Brian Flores", "Chad O'Shea"),
        2020: ("Brian Flores", "Chan Gailey"),
        2021: ("Brian Flores", "George Godsey"),
        2022: ("Mike McDaniel", "Frank Smith"),
        2023: ("Mike McDaniel", "Frank Smith"),
    },
    "MIN": {
        2014: ("Mike Zimmer", "Norv Turner"),
        2015: ("Mike Zimmer", "Norv Turner"),
        2016: ("Mike Zimmer", "Norv Turner"),
        2017: ("Mike Zimmer", "Pat Shurmur"),
        2018: ("Mike Zimmer", "John DeFilippo"),
        2019: ("Mike Zimmer", "Kevin Stefanski"),
        2020: ("Mike Zimmer", "Gary Kubiak"),
        2021: ("Mike Zimmer", "Klint Kubiak"),
        2022: ("Kevin O'Connell", "Wes Phillips"),
        2023: ("Kevin O'Connell", "Wes Phillips"),
    },
    "NE": {
        2014: ("Bill Belichick", "Josh McDaniels"),
        2015: ("Bill Belichick", "Josh McDaniels"),
        2016: ("Bill Belichick", "Josh McDaniels"),
        2017: ("Bill Belichick", "Josh McDaniels"),
        2018: ("Bill Belichick", "Josh McDaniels"),
        2019: ("Bill Belichick", "Josh McDaniels"),
        2020: ("Bill Belichick", "Josh McDaniels"),
        2021: ("Bill Belichick", "Josh McDaniels"),
        2022: ("Bill Belichick", "Matt Patricia"),
        2023: ("Bill Belichick", "Bill O'Brien"),
    },
    "NO": {
        2014: ("Sean Payton", "Pete Carmichael"),
        2015: ("Sean Payton", "Pete Carmichael"),
        2016: ("Sean Payton", "Pete Carmichael"),
        2017: ("Sean Payton", "Pete Carmichael"),
        2018: ("Sean Payton", "Pete Carmichael"),
        2019: ("Sean Payton", "Pete Carmichael"),
        2020: ("Sean Payton", "Pete Carmichael"),
        2021: ("Sean Payton", "Pete Carmichael"),
        2022: ("Dennis Allen", "Pete Carmichael"),
        2023: ("Dennis Allen", "Pete Carmichael"),
    },
    "NYG": {
        2014: ("Tom Coughlin", "Ben McAdoo"),
        2015: ("Tom Coughlin", "Ben McAdoo"),
        2016: ("Ben McAdoo", "Mike Sullivan"),
        2017: ("Ben McAdoo", "Mike Sullivan"),
        2018: ("Pat Shurmur", "Mike Shula"),
        2019: ("Pat Shurmur", "Mike Shula"),
        2020: ("Joe Judge", "Jason Garrett"),
        2021: ("Joe Judge", "Jason Garrett"),
        2022: ("Brian Daboll", "Mike Kafka"),
        2023: ("Brian Daboll", "Mike Kafka"),
    },
    "NYJ": {
        2014: ("Rex Ryan", "Marty Mornhinweg"),
        2015: ("Todd Bowles", "Chan Gailey"),
        2016: ("Todd Bowles", "Chan Gailey"),
        2017: ("Todd Bowles", "John Morton"),
        2018: ("Todd Bowles", "Jeremy Bates"),
        2019: ("Adam Gase", "Dowell Loggains"),
        2020: ("Adam Gase", "Dowell Loggains"),
        2021: ("Robert Saleh", "Mike LaFleur"),
        2022: ("Robert Saleh", "Mike LaFleur"),
        2023: ("Robert Saleh", "Nathaniel Hackett"),
    },
    "PHI": {
        2014: ("Chip Kelly", "Pat Shurmur"),
        2015: ("Chip Kelly", "Pat Shurmur"),
        2016: ("Doug Pederson", "Frank Reich"),
        2017: ("Doug Pederson", "Frank Reich"),
        2018: ("Doug Pederson", "Mike Groh"),
        2019: ("Doug Pederson", "Mike Groh"),
        2020: ("Doug Pederson", "Press Taylor"),
        2021: ("Nick Sirianni", "Shane Steichen"),
        2022: ("Nick Sirianni", "Shane Steichen"),
        2023: ("Nick Sirianni", "Brian Johnson"),
    },
    "PIT": {
        2014: ("Mike Tomlin", "Todd Haley"),
        2015: ("Mike Tomlin", "Todd Haley"),
        2016: ("Mike Tomlin", "Todd Haley"),
        2017: ("Mike Tomlin", "Todd Haley"),
        2018: ("Mike Tomlin", "Randy Fichtner"),
        2019: ("Mike Tomlin", "Randy Fichtner"),
        2020: ("Mike Tomlin", "Randy Fichtner"),
        2021: ("Mike Tomlin", "Matt Canada"),
        2022: ("Mike Tomlin", "Matt Canada"),
        2023: ("Mike Tomlin", "Matt Canada"),
    },
    "SEA": {
        2014: ("Pete Carroll", "Darrell Bevell"),
        2015: ("Pete Carroll", "Darrell Bevell"),
        2016: ("Pete Carroll", "Darrell Bevell"),
        2017: ("Pete Carroll", "Darrell Bevell"),
        2018: ("Pete Carroll", "Brian Schottenheimer"),
        2019: ("Pete Carroll", "Brian Schottenheimer"),
        2020: ("Pete Carroll", "Brian Schottenheimer"),
        2021: ("Pete Carroll", "Shane Waldron"),
        2022: ("Pete Carroll", "Shane Waldron"),
        2023: ("Pete Carroll", "Shane Waldron"),
    },
    "SF": {
        2014: ("Jim Harbaugh", "Greg Roman"),
        2015: ("Jim Tomsula", "Geep Chryst"),
        2016: ("Chip Kelly", "Curtis Modkins"),
        2017: ("Kyle Shanahan", "Kyle Shanahan"),
        2018: ("Kyle Shanahan", "Kyle Shanahan"),
        2019: ("Kyle Shanahan", "Kyle Shanahan"),
        2020: ("Kyle Shanahan", "Kyle Shanahan"),
        2021: ("Kyle Shanahan", "Kyle Shanahan"),
        2022: ("Kyle Shanahan", "Kyle Shanahan"),
        2023: ("Kyle Shanahan", "Kyle Shanahan"),
    },
    "TB": {
        2014: ("Lovie Smith", "Jeff Tedford"),
        2015: ("Lovie Smith", "Dirk Koetter"),
        2016: ("Dirk Koetter", "Todd Monken"),
        2017: ("Dirk Koetter", "Todd Monken"),
        2018: ("Dirk Koetter", "Todd Monken"),
        2019: ("Bruce Arians", "Byron Leftwich"),
        2020: ("Bruce Arians", "Byron Leftwich"),
        2021: ("Bruce Arians", "Byron Leftwich"),
        2022: ("Todd Bowles", "Byron Leftwich"),
        2023: ("Todd Bowles", "Dave Canales"),
    },
    "TEN": {
        2014: ("Ken Whisenhunt", "Jason Michael"),
        2015: ("Ken Whisenhunt", "Jason Michael"),
        2016: ("Mike Mularkey", "Terry Robiskie"),
        2017: ("Mike Mularkey", "Terry Robiskie"),
        2018: ("Mike Vrabel", "Matt LaFleur"),
        2019: ("Mike Vrabel", "Arthur Smith"),
        2020: ("Mike Vrabel", "Arthur Smith"),
        2021: ("Mike Vrabel", "Todd Downing"),
        2022: ("Mike Vrabel", "Todd Downing"),
        2023: ("Mike Vrabel", "Tim Kelly"),
    },
    "WAS": {
        2014: ("Jay Gruden", "Sean McVay"),
        2015: ("Jay Gruden", "Sean McVay"),
        2016: ("Jay Gruden", "Sean McVay"),
        2017: ("Jay Gruden", "Matt Cavanaugh"),
        2018: ("Jay Gruden", "Matt Cavanaugh"),
        2019: ("Jay Gruden", "Kevin O'Connell"),
        2020: ("Ron Rivera", "Scott Turner"),
        2021: ("Ron Rivera", "Scott Turner"),
        2022: ("Ron Rivera", "Scott Turner"),
        2023: ("Ron Rivera", "Eric Bieniemy"),
    },
}

# System tag mapping by coaching tree
SYSTEM_TAGS = {
    "Kyle Shanahan": "SHANAHAN_ZONE",
    "Matt LaFleur": "SHANAHAN_ZONE",
    "Kevin O'Connell": "MCVAY_TREE",
    "Mike McDaniel": "SHANAHAN_ZONE",
    "DeMeco Ryans": "SHANAHAN_ZONE",
    "Kevin Stefanski": "SHANAHAN_ZONE",
    "Klint Kubiak": "SHANAHAN_ZONE",
    "Gary Kubiak": "SHANAHAN_ZONE",
    "Sean McVay": "MCVAY_TREE",
    "Zac Taylor": "MCVAY_TREE",
    "Brandon Staley": "MCVAY_TREE",
    "Dave Canales": "MCVAY_TREE",
    "Brian Callahan": "MCVAY_TREE",
    "Andy Reid": "REID_WEST_COAST",
    "Doug Pederson": "REID_WEST_COAST",
    "Matt Nagy": "REID_WEST_COAST",
    "Shane Steichen": "REID_WEST_COAST",
    "Nick Sirianni": "REID_WEST_COAST",
    "Frank Reich": "REID_WEST_COAST",
    "Kliff Kingsbury": "AIR_RAID",
}


# Starting QBs by team and season (primary starter, most games_started)
STARTING_QBS: dict[str, dict[int, str]] = {
    "ARI": {2014: "Carson Palmer", 2015: "Carson Palmer", 2016: "Carson Palmer",
            2017: "Carson Palmer", 2018: "Josh Rosen", 2019: "Kyler Murray",
            2020: "Kyler Murray", 2021: "Kyler Murray", 2022: "Kyler Murray",
            2023: "Kyler Murray"},
    "ATL": {2014: "Matt Ryan", 2015: "Matt Ryan", 2016: "Matt Ryan",
            2017: "Matt Ryan", 2018: "Matt Ryan", 2019: "Matt Ryan",
            2020: "Matt Ryan", 2021: "Matt Ryan", 2022: "Marcus Mariota",
            2023: "Desmond Ridder"},
    "BAL": {2014: "Joe Flacco", 2015: "Joe Flacco", 2016: "Joe Flacco",
            2017: "Joe Flacco", 2018: "Lamar Jackson", 2019: "Lamar Jackson",
            2020: "Lamar Jackson", 2021: "Lamar Jackson", 2022: "Lamar Jackson",
            2023: "Lamar Jackson"},
    "BUF": {2014: "Kyle Orton", 2015: "Tyrod Taylor", 2016: "Tyrod Taylor",
            2017: "Tyrod Taylor", 2018: "Josh Allen", 2019: "Josh Allen",
            2020: "Josh Allen", 2021: "Josh Allen", 2022: "Josh Allen",
            2023: "Josh Allen"},
    "CAR": {2014: "Cam Newton", 2015: "Cam Newton", 2016: "Cam Newton",
            2017: "Cam Newton", 2018: "Cam Newton", 2019: "Kyle Allen",
            2020: "Teddy Bridgewater", 2021: "Sam Darnold", 2022: "Sam Darnold",
            2023: "Bryce Young"},
    "CHI": {2014: "Jay Cutler", 2015: "Jay Cutler", 2016: "Jay Cutler",
            2017: "Mitchell Trubisky", 2018: "Mitchell Trubisky",
            2019: "Mitchell Trubisky", 2020: "Nick Foles", 2021: "Justin Fields",
            2022: "Justin Fields", 2023: "Justin Fields"},
    "CIN": {2014: "Andy Dalton", 2015: "Andy Dalton", 2016: "Andy Dalton",
            2017: "Andy Dalton", 2018: "Andy Dalton", 2019: "Andy Dalton",
            2020: "Joe Burrow", 2021: "Joe Burrow", 2022: "Joe Burrow",
            2023: "Joe Burrow"},
    "CLE": {2014: "Brian Hoyer", 2015: "Josh McCown", 2016: "Robert Griffin III",
            2017: "DeShone Kizer", 2018: "Baker Mayfield", 2019: "Baker Mayfield",
            2020: "Baker Mayfield", 2021: "Baker Mayfield", 2022: "Jacoby Brissett",
            2023: "Deshaun Watson"},
    "DAL": {2014: "Tony Romo", 2015: "Tony Romo", 2016: "Dak Prescott",
            2017: "Dak Prescott", 2018: "Dak Prescott", 2019: "Dak Prescott",
            2020: "Dak Prescott", 2021: "Dak Prescott", 2022: "Dak Prescott",
            2023: "Dak Prescott"},
    "DEN": {2014: "Peyton Manning", 2015: "Peyton Manning", 2016: "Trevor Siemian",
            2017: "Trevor Siemian", 2018: "Case Keenum", 2019: "Joe Flacco",
            2020: "Drew Lock", 2021: "Teddy Bridgewater", 2022: "Russell Wilson",
            2023: "Russell Wilson"},
    "DET": {2014: "Matthew Stafford", 2015: "Matthew Stafford", 2016: "Matthew Stafford",
            2017: "Matthew Stafford", 2018: "Matthew Stafford",
            2019: "Matthew Stafford", 2020: "Matthew Stafford",
            2021: "Jared Goff", 2022: "Jared Goff", 2023: "Jared Goff"},
    "GB":  {2014: "Aaron Rodgers", 2015: "Aaron Rodgers", 2016: "Aaron Rodgers",
            2017: "Aaron Rodgers", 2018: "Aaron Rodgers", 2019: "Aaron Rodgers",
            2020: "Aaron Rodgers", 2021: "Aaron Rodgers", 2022: "Aaron Rodgers",
            2023: "Jordan Love"},
    "HOU": {2014: "Ryan Fitzpatrick", 2015: "Brian Hoyer", 2016: "Brock Osweiler",
            2017: "Deshaun Watson", 2018: "Deshaun Watson", 2019: "Deshaun Watson",
            2020: "Deshaun Watson", 2021: "Tyrod Taylor", 2022: "Davis Mills",
            2023: "CJ Stroud"},
    "IND": {2014: "Andrew Luck", 2015: "Andrew Luck", 2016: "Andrew Luck",
            2017: "Jacoby Brissett", 2018: "Andrew Luck", 2019: "Jacoby Brissett",
            2020: "Philip Rivers", 2021: "Carson Wentz", 2022: "Matt Ryan",
            2023: "Gardner Minshew"},
    "JAX": {2014: "Blake Bortles", 2015: "Blake Bortles", 2016: "Blake Bortles",
            2017: "Blake Bortles", 2018: "Blake Bortles", 2019: "Gardner Minshew",
            2020: "Gardner Minshew", 2021: "Trevor Lawrence", 2022: "Trevor Lawrence",
            2023: "Trevor Lawrence"},
    "KC":  {2014: "Alex Smith", 2015: "Alex Smith", 2016: "Alex Smith",
            2017: "Alex Smith", 2018: "Patrick Mahomes", 2019: "Patrick Mahomes",
            2020: "Patrick Mahomes", 2021: "Patrick Mahomes",
            2022: "Patrick Mahomes", 2023: "Patrick Mahomes"},
    "LAC": {2014: "Philip Rivers", 2015: "Philip Rivers", 2016: "Philip Rivers",
            2017: "Philip Rivers", 2018: "Philip Rivers", 2019: "Philip Rivers",
            2020: "Justin Herbert", 2021: "Justin Herbert", 2022: "Justin Herbert",
            2023: "Justin Herbert"},
    "LAR": {2014: "Shaun Hill", 2015: "Nick Foles", 2016: "Jared Goff",
            2017: "Jared Goff", 2018: "Jared Goff", 2019: "Jared Goff",
            2020: "Jared Goff", 2021: "Matthew Stafford", 2022: "Matthew Stafford",
            2023: "Matthew Stafford"},
    "LV":  {2014: "Derek Carr", 2015: "Derek Carr", 2016: "Derek Carr",
            2017: "Derek Carr", 2018: "Derek Carr", 2019: "Derek Carr",
            2020: "Derek Carr", 2021: "Derek Carr", 2022: "Derek Carr",
            2023: "Jimmy Garoppolo"},
    "MIA": {2014: "Ryan Tannehill", 2015: "Ryan Tannehill", 2016: "Ryan Tannehill",
            2017: "Jay Cutler", 2018: "Ryan Tannehill", 2019: "Ryan Fitzpatrick",
            2020: "Tua Tagovailoa", 2021: "Tua Tagovailoa", 2022: "Tua Tagovailoa",
            2023: "Tua Tagovailoa"},
    "MIN": {2014: "Teddy Bridgewater", 2015: "Teddy Bridgewater",
            2016: "Sam Bradford", 2017: "Case Keenum", 2018: "Kirk Cousins",
            2019: "Kirk Cousins", 2020: "Kirk Cousins", 2021: "Kirk Cousins",
            2022: "Kirk Cousins", 2023: "Kirk Cousins"},
    "NE":  {2014: "Tom Brady", 2015: "Tom Brady", 2016: "Tom Brady",
            2017: "Tom Brady", 2018: "Tom Brady", 2019: "Tom Brady",
            2020: "Cam Newton", 2021: "Mac Jones", 2022: "Mac Jones",
            2023: "Mac Jones"},
    "NO":  {2014: "Drew Brees", 2015: "Drew Brees", 2016: "Drew Brees",
            2017: "Drew Brees", 2018: "Drew Brees", 2019: "Drew Brees",
            2020: "Drew Brees", 2021: "Jameis Winston", 2022: "Andy Dalton",
            2023: "Derek Carr"},
    "NYG": {2014: "Eli Manning", 2015: "Eli Manning", 2016: "Eli Manning",
            2017: "Eli Manning", 2018: "Eli Manning", 2019: "Daniel Jones",
            2020: "Daniel Jones", 2021: "Daniel Jones", 2022: "Daniel Jones",
            2023: "Daniel Jones"},
    "NYJ": {2014: "Geno Smith", 2015: "Ryan Fitzpatrick", 2016: "Ryan Fitzpatrick",
            2017: "Josh McCown", 2018: "Sam Darnold", 2019: "Sam Darnold",
            2020: "Sam Darnold", 2021: "Zach Wilson", 2022: "Zach Wilson",
            2023: "Zach Wilson"},
    "PHI": {2014: "Nick Foles", 2015: "Sam Bradford", 2016: "Carson Wentz",
            2017: "Carson Wentz", 2018: "Carson Wentz", 2019: "Carson Wentz",
            2020: "Carson Wentz", 2021: "Jalen Hurts", 2022: "Jalen Hurts",
            2023: "Jalen Hurts"},
    "PIT": {2014: "Ben Roethlisberger", 2015: "Ben Roethlisberger",
            2016: "Ben Roethlisberger", 2017: "Ben Roethlisberger",
            2018: "Ben Roethlisberger", 2019: "Mason Rudolph",
            2020: "Ben Roethlisberger", 2021: "Ben Roethlisberger",
            2022: "Kenny Pickett", 2023: "Kenny Pickett"},
    "SEA": {2014: "Russell Wilson", 2015: "Russell Wilson", 2016: "Russell Wilson",
            2017: "Russell Wilson", 2018: "Russell Wilson", 2019: "Russell Wilson",
            2020: "Russell Wilson", 2021: "Russell Wilson", 2022: "Geno Smith",
            2023: "Geno Smith"},
    "SF":  {2014: "Colin Kaepernick", 2015: "Colin Kaepernick",
            2016: "Colin Kaepernick", 2017: "Jimmy Garoppolo",
            2018: "Jimmy Garoppolo", 2019: "Jimmy Garoppolo",
            2020: "Jimmy Garoppolo", 2021: "Jimmy Garoppolo",
            2022: "Jimmy Garoppolo", 2023: "Brock Purdy"},
    "TB":  {2014: "Josh McCown", 2015: "Jameis Winston", 2016: "Jameis Winston",
            2017: "Jameis Winston", 2018: "Jameis Winston", 2019: "Jameis Winston",
            2020: "Tom Brady", 2021: "Tom Brady", 2022: "Tom Brady",
            2023: "Baker Mayfield"},
    "TEN": {2014: "Jake Locker", 2015: "Marcus Mariota", 2016: "Marcus Mariota",
            2017: "Marcus Mariota", 2018: "Marcus Mariota", 2019: "Ryan Tannehill",
            2020: "Ryan Tannehill", 2021: "Ryan Tannehill", 2022: "Ryan Tannehill",
            2023: "Ryan Tannehill"},
    "WAS": {2014: "Robert Griffin III", 2015: "Kirk Cousins", 2016: "Kirk Cousins",
            2017: "Kirk Cousins", 2018: "Alex Smith", 2019: "Case Keenum",
            2020: "Alex Smith", 2021: "Taylor Heinicke", 2022: "Carson Wentz",
            2023: "Sam Howell"},
}


def get_system_tag(hc: str) -> str:
    return SYSTEM_TAGS.get(hc, "OTHER")


def build_coaching_history() -> list[dict]:
    """Build coaching staff records for 2014-2023 with computed continuity flags."""
    records = []

    for team, seasons in sorted(COACHING_DATA.items()):
        prev_hc = None
        prev_oc = None
        prev_qb = None
        hc_tenure = 0
        oc_tenure = 0

        team_qbs = STARTING_QBS.get(team, {})

        for season in sorted(seasons.keys()):
            hc, oc = seasons[season]
            qb = team_qbs.get(season)

            if hc == prev_hc:
                hc_continuity = 1
                hc_tenure += 1
            else:
                hc_continuity = 0
                hc_tenure = 1

            if oc == prev_oc:
                oc_continuity = 1
                oc_tenure += 1
            else:
                oc_continuity = 0
                oc_tenure = 1

            if prev_qb is None or qb == prev_qb:
                qb_continuity = 1
            else:
                qb_continuity = 0

            record = {
                "team": team,
                "season": season,
                "head_coach": hc,
                "offensive_coordinator": oc,
                "hc_year_with_team": hc_tenure,
                "oc_year_with_team": oc_tenure,
                "hc_continuity_flag": hc_continuity,
                "oc_continuity_flag": oc_continuity,
                "system_tag": get_system_tag(hc),
            }
            if qb:
                record["starting_qb"] = qb
                record["qb_continuity_flag"] = qb_continuity

            records.append(record)

            prev_hc = hc
            prev_oc = oc
            prev_qb = qb

    return records


def main():
    records = build_coaching_history()
    out_path = Path(__file__).resolve().parents[1] / "data" / "coaching_staff_historical.json"
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)

    # Summary
    seasons = sorted(set(r["season"] for r in records))
    print(f"Generated {len(records)} coaching staff records")
    print(f"Seasons: {seasons[0]}-{seasons[-1]}")
    print(f"Teams: {len(set(r['team'] for r in records))}")

    # Count continuity flags
    hc_changes = sum(1 for r in records if r["hc_continuity_flag"] == 0)
    oc_changes = sum(1 for r in records if r["oc_continuity_flag"] == 0)
    qb_changes = sum(1 for r in records if r.get("qb_continuity_flag") == 0)
    print(f"HC changes (continuity=0): {hc_changes}")
    print(f"OC changes (continuity=0): {oc_changes}")
    print(f"QB changes (continuity=0): {qb_changes}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
