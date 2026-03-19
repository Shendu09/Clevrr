"""Strategic memory compaction inspired by ECC strategic-compact."""


class MemoryOptimizer:
    """Decides when to compact memory and performs lightweight cleanup."""

    def __init__(self, memory_system):
        self.memory = memory_system
        self.MAX_EPISODES = 500
        self.COMPACT_THRESHOLD = 0.8

    def should_compact(self) -> bool:
        stats = self.memory.get_stats()
        total = stats.get("total_episodes", 0)
        return total > (self.MAX_EPISODES * self.COMPACT_THRESHOLD)

    def compact_memory(self):
        stats = self.memory.get_stats()

        if not self.should_compact():
            return {"compacted": False}

        if hasattr(self.memory, "clear_old_episodes"):
            self.memory.clear_old_episodes(days=7)

        return {
            "compacted": True,
            "before": stats.get("total_episodes", 0),
            "after": self.memory.get_stats().get("total_episodes", 0),
        }

    def get_memory_health(self) -> dict:
        stats = self.memory.get_stats()
        total = stats.get("total_episodes", 0)
        usage = total / self.MAX_EPISODES

        if usage < 0.5:
            status = "Healthy"
        elif usage < 0.8:
            status = "Getting Full"
        else:
            status = "Needs Compaction"

        return {
            "status": status,
            "usage_percent": usage * 100,
            "total_episodes": total,
            "recommendation": (
                "Compact memory" if usage > 0.8 else "No action needed"
            ),
        }
