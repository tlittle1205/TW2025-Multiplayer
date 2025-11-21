# game/world/stardock.py
"""
Stardock services and interactions for TradeWars 2025.

The Celestial Bazaar (Stardock) offers various services:
- Corporate Concourse: Ship upgrades and repairs
- Interstellar Bank: Credit storage and management
- Rusty Nebula: Gambling and rumors
- Market Promenade: Future exotic goods trading
- Tech Lab: Future experimental modifications
"""

import random
from typing import Any, Dict, List, Optional

# ------------------------------------------------------------
# Response Builder
# ------------------------------------------------------------

def _result(
    success: bool,
    message: str,
    lines: Optional[List[str]] = None,
    player_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build standardized response packet for stardock actions.
    
    Args:
        success: Whether the action succeeded
        message: Main status message
        lines: Additional detail lines (for multi-line responses)
        player_state: Updated player state dict
    
    Returns:
        Response dict matching DOCK_ACTION packet format
    """
    return {
        "success": success,
        "message": message,
        "lines": lines or [],
        "player_state": player_state or {},
    }


# ------------------------------------------------------------
# Rumors for Rusty Nebula
# ------------------------------------------------------------

RUMORS = [
    "A rogue AI ship was spotted near sector 12—likes to hack nav-computers.",
    "A hidden wormhole near sector 17 took a scout ship. Didn't bring it back.",
    "Corporate transport vanished near the rim—pirates or slavers.",
    "A planet with insane organic production is stirring corporate wars.",
    "Some sectors aren't what they seem… especially the uncharted ones.",
    "Word is there's a cache of military-grade equipment in the outer sectors.",
    "Fuel prices are about to spike—corporate fleet movements detected.",
    "A derelict station was found drifting. Nobody aboard. Nobody.",
    "Black market ore has been flooding sector 45. Someone's mining illegally.",
    "The banking guild is watching transactions over 100k credits closely.",
    "A pirate lord is offering bounties for corporate ships. Big money.",
    "Experimental jump drives have been stolen from Tech Lab storage.",
    "Some trader made 50k credits in one run. Either genius or lucky.",
    "Port authorities in sector 88 are suspiciously lax with inspections.",
    "A ghost ship keeps appearing on scanners but vanishes when approached.",
]


# ------------------------------------------------------------
# Service Pricing and Constants
# ------------------------------------------------------------

# Corporate Concourse pricing
HULL_REPAIR_COST = 150
HULL_REPAIR_AMOUNT = 10

SHIELD_UPGRADE_COST = 500
SHIELD_UPGRADE_AMOUNT = 5

CARGO_EXPANSION_COST = 5000
CARGO_EXPANSION_AMOUNT = 5

# Gambling parameters
GAMBLE_WIN_CHANCE = 50  # 50% chance to win
GAMBLE_WIN_MULTIPLIER = 2  # Win 2x your bet


# ------------------------------------------------------------
# Main Stardock Action Processor
# ------------------------------------------------------------

def stardock_process_action(
    action: str,
    params: Dict[str, Any],
    player: Dict[str, Any],
    galaxy: Any,
) -> Dict[str, Any]:
    """
    Process all stardock service actions.
    
    Args:
        action: Action identifier (e.g., "REPAIR_HULL", "BANK_DEPOSIT")
        params: Additional parameters for the action
        player: Player state dictionary (modified in-place)
        galaxy: Galaxy instance (for future features)
    
    Returns:
        Response dict matching DOCK_ACTION packet format with:
        - success: bool
        - message: str
        - lines: List[str] (optional additional info)
        - player_state: Dict (updated player state)
    """

    # ==================================================================
    # CORPORATE CONCOURSE - Ship Maintenance & Upgrades
    # ==================================================================

    if action == "REPAIR_HULL":
        """Repair ship hull damage."""
        current_hull = player.get("hull", 100)
        
        # Check if repair is needed
        if current_hull >= 100:
            return _result(
                False,
                "Hull integrity at maximum. No repairs needed.",
                player_state=player,
            )
        
        # Check credits
        if player.get("credits", 0) < HULL_REPAIR_COST:
            return _result(
                False,
                f"Not enough credits. Hull repair costs {HULL_REPAIR_COST} credits.",
                player_state=player,
            )

        # Apply repair
        player["credits"] -= HULL_REPAIR_COST
        player["hull"] = min(current_hull + HULL_REPAIR_AMOUNT, 100)
        actual_repair = player["hull"] - current_hull

        return _result(
            True,
            f"Hull repaired +{actual_repair}%. Integrity now at {player['hull']}%.",
            lines=[
                "Nano-welders seal the breaches with surgical precision.",
                f"Cost: {HULL_REPAIR_COST} credits."
            ],
            player_state=player,
        )

    if action == "UPGRADE_SHIELDS":
        """Upgrade shield capacity."""
        if player.get("credits", 0) < SHIELD_UPGRADE_COST:
            return _result(
                False,
                f"Insufficient credits. Shield upgrade costs {SHIELD_UPGRADE_COST} credits.",
                player_state=player,
            )

        # Apply upgrade
        player["credits"] -= SHIELD_UPGRADE_COST
        player["shields"] = player.get("shields", 10) + SHIELD_UPGRADE_AMOUNT

        return _result(
            True,
            f"Shield capacity increased by {SHIELD_UPGRADE_AMOUNT}. Total: {player['shields']}.",
            lines=[
                "Capacitors hum as the new shield emitters come online.",
                f"Cost: {SHIELD_UPGRADE_COST} credits."
            ],
            player_state=player,
        )

    if action == "EXPAND_CARGO":
        """Expand cargo hold capacity."""
        if player.get("credits", 0) < CARGO_EXPANSION_COST:
            return _result(
                False,
                f"Not enough credits. Cargo expansion costs {CARGO_EXPANSION_COST} credits.",
                player_state=player,
            )

        # Apply expansion
        player["credits"] -= CARGO_EXPANSION_COST
        player["holds"] = player.get("holds", 100) + CARGO_EXPANSION_AMOUNT

        return _result(
            True,
            f"Cargo holds expanded by {CARGO_EXPANSION_AMOUNT}. Total: {player['holds']}.",
            lines=[
                "Engineering crews install modular storage units.",
                "Your ship's mass increases slightly but the extra space is worth it.",
                f"Cost: {CARGO_EXPANSION_COST} credits."
            ],
            player_state=player,
        )

    # ==================================================================
    # INTERSTELLAR BANK - Credit Management
    # ==================================================================

    if action == "BANK_DEPOSIT":
        """Deposit credits into secure bank account."""
        amount = params.get("amount", 0)

        # Validate amount
        if amount <= 0:
            return _result(
                False,
                "Invalid deposit amount. Must be greater than 0.",
                player_state=player,
            )

        # Check available credits
        if player.get("credits", 0) < amount:
            return _result(
                False,
                f"Insufficient credits. You have {player.get('credits', 0)} credits available.",
                player_state=player,
            )

        # Process deposit
        player["credits"] -= amount
        player["bank"] = player.get("bank", 0) + amount

        return _result(
            True,
            f"Deposited {amount:,} credits.",
            lines=[
                f"Bank balance: {player['bank']:,} credits",
                f"Cash on hand: {player['credits']:,} credits",
                "Funds are protected by military-grade encryption."
            ],
            player_state=player,
        )

    if action == "BANK_WITHDRAW":
        """Withdraw credits from bank account."""
        amount = params.get("amount", 0)

        # Validate amount
        if amount <= 0:
            return _result(
                False,
                "Invalid withdrawal amount. Must be greater than 0.",
                player_state=player,
            )

        # Check bank balance
        bank_balance = player.get("bank", 0)
        if bank_balance < amount:
            return _result(
                False,
                f"Insufficient bank balance. You have {bank_balance:,} credits in the bank.",
                player_state=player,
            )

        # Process withdrawal
        player["bank"] -= amount
        player["credits"] = player.get("credits", 0) + amount

        return _result(
            True,
            f"Withdrew {amount:,} credits.",
            lines=[
                f"Bank balance: {player['bank']:,} credits",
                f"Cash on hand: {player['credits']:,} credits",
                "Credits transferred to your ship's vault."
            ],
            player_state=player,
        )

    if action == "BANK_BALANCE":
        """Check bank account balance."""
        bank_balance = player.get("bank", 0)
        credits = player.get("credits", 0)
        total = bank_balance + credits

        return _result(
            True,
            "Account summary:",
            lines=[
                f"Bank balance: {bank_balance:,} credits",
                f"Cash on hand: {credits:,} credits",
                f"Total assets: {total:,} credits",
            ],
            player_state=player,
        )

    # ==================================================================
    # RUSTY NEBULA - Cantina Services
    # ==================================================================

    if action == "RUSTY_RUMOR":
        """Hear a random rumor from the cantina."""
        rumor = random.choice(RUMORS)
        
        return _result(
            True,
            "A hooded figure leans close and whispers...",
            lines=[
                "",
                f'"{rumor}"',
                "",
                "They disappear back into the smoky crowd."
            ],
            player_state=player,
        )

    if action == "RUSTY_GAMBLE":
        """Gamble credits in a game of chance."""
        amount = params.get("amount", 0)

        # Validate bet amount
        if amount <= 0:
            return _result(
                False,
                "Invalid bet amount. Must be greater than 0.",
                player_state=player,
            )

        # Check available credits
        if player.get("credits", 0) < amount:
            return _result(
                False,
                f"Not enough credits to gamble. You have {player.get('credits', 0)} credits.",
                player_state=player,
            )

        # Deduct bet
        player["credits"] -= amount

        # Roll the dice
        roll = random.randint(1, 100)
        won = roll <= GAMBLE_WIN_CHANCE

        if won:
            winnings = amount * GAMBLE_WIN_MULTIPLIER
            player["credits"] += winnings
            profit = winnings - amount
            
            return _result(
                True,
                f"YOU WON! The house pays out {winnings:,} credits.",
                lines=[
                    f"You bet {amount:,} and won {profit:,} credits!",
                    "The dealer nods with grudging respect.",
                    f"Credits: {player['credits']:,}"
                ],
                player_state=player,
            )
        else:
            return _result(
                False,
                f"You lost. The house takes your {amount:,} credits.",
                lines=[
                    "The cards weren't in your favor this time.",
                    "The dealer smirks and slides your chips away.",
                    f"Credits: {player['credits']:,}"
                ],
                player_state=player,
            )

    if action == "RUSTY_DRINKS":
        """Buy drinks at the cantina (cosmetic/future feature)."""
        drink_cost = 10
        
        if player.get("credits", 0) < drink_cost:
            return _result(
                False,
                "Not enough credits for a drink.",
                player_state=player,
            )
        
        player["credits"] -= drink_cost
        
        drinks = [
            "Pan-Galactic Gargle Blaster",
            "Sirius Cybertonic",
            "Nebula Fizz",
            "Void Whiskey",
            "Asteroid Ale",
        ]
        
        drink = random.choice(drinks)
        
        return _result(
            True,
            f"You order a {drink}.",
            lines=[
                "The bartender slides it across the counter.",
                "It tastes like regret and stardust.",
                f"Cost: {drink_cost} credits"
            ],
            player_state=player,
        )

    # ==================================================================
    # MARKET PROMENADE - Future Feature
    # ==================================================================

    if action == "MARKET_BROWSE":
        """Browse exotic market goods (placeholder)."""
        return _result(
            True,
            "Market Promenade coming soon!",
            lines=[
                "Exotic goods, rare artifacts, and black market tech.",
                "Under construction. Check back later."
            ],
            player_state=player,
        )

    # ==================================================================
    # TECH LAB - Future Feature
    # ==================================================================

    if action == "TECH_BROWSE":
        """Browse experimental modifications (placeholder)."""
        return _result(
            True,
            "Tech Lab experimental mods coming soon!",
            lines=[
                "Jump drive enhancers, cloaking devices, weapon systems.",
                "Currently in development. Stand by."
            ],
            player_state=player,
        )

    # ==================================================================
    # UNKNOWN ACTION
    # ==================================================================

    return _result(
        False,
        f"Unknown Stardock action: '{action}'",
        lines=[
            "Available actions:",
            "REPAIR_HULL, UPGRADE_SHIELDS, EXPAND_CARGO",
            "BANK_DEPOSIT, BANK_WITHDRAW, BANK_BALANCE",
            "RUSTY_RUMOR, RUSTY_GAMBLE, RUSTY_DRINKS",
        ],
        player_state=player,
    )


# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------

def get_service_menu(service_area: str) -> List[str]:
    """
    Get available actions for a specific service area.
    
    Args:
        service_area: Service identifier (e.g., "corporate", "bank", "rusty")
    
    Returns:
        List of available actions for that area
    """
    menus = {
        "corporate": [
            "REPAIR_HULL - Repair hull damage (150 credits)",
            "UPGRADE_SHIELDS - Increase shield capacity (500 credits)",
            "EXPAND_CARGO - Add cargo holds (5000 credits)",
        ],
        "bank": [
            "BANK_DEPOSIT <amount> - Deposit credits",
            "BANK_WITHDRAW <amount> - Withdraw credits",
            "BANK_BALANCE - Check account balance",
        ],
        "rusty": [
            "RUSTY_RUMOR - Hear rumors (free)",
            "RUSTY_GAMBLE <amount> - Gamble credits",
            "RUSTY_DRINKS - Buy a drink (10 credits)",
        ],
        "market": [
            "MARKET_BROWSE - Browse exotic goods (coming soon)",
        ],
        "tech": [
            "TECH_BROWSE - View experimental mods (coming soon)",
        ],
    }
    
    return menus.get(service_area.lower(), [])


def get_stardock_info() -> Dict[str, Any]:
    """
    Get general information about Stardock services.
    
    Returns:
        Dict containing service descriptions and pricing
    """
    return {
        "name": "Celestial Bazaar Stardock",
        "description": "Premium services for discerning captains",
        "services": {
            "Corporate Concourse": {
                "description": "Ship upgrades and maintenance",
                "services": get_service_menu("corporate"),
            },
            "Interstellar Bank": {
                "description": "Secure credit storage",
                "services": get_service_menu("bank"),
            },
            "Rusty Nebula": {
                "description": "Cantina and entertainment",
                "services": get_service_menu("rusty"),
            },
            "Market Promenade": {
                "description": "Exotic goods trading",
                "services": get_service_menu("market"),
            },
            "Tech Lab": {
                "description": "Experimental modifications",
                "services": get_service_menu("tech"),
            },
        },
    }