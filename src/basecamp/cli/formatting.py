SPORT_GROUPS = {
    "Ride": ["Ride", "VirtualRide"],
    "Run": ["Run", "TrailRun"],
    "Swim": ["Swim"],
}


def sport_group(sport_type: str) -> str:
    for group, types in SPORT_GROUPS.items():
        if sport_type in types:
            return group
    return "Other"


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"
