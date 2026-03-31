"""Tests for Screenshot Manager System
=====================================

Tests screenshot comparison, change detection, and caching.
"""

import pytest
from core.screen.screenshot_manager import (
    ScreenshotMetadata,
    ScreenshotComparator,
    ScreenshotCache
)


class TestScreenshotMetadata:
    """Tests for ScreenshotMetadata dataclass."""
    
    def test_metadata_creation(self):
        """Test creating metadata."""
        meta = ScreenshotMetadata(
            hash="abc123def456",
            size=1024,
            width=1920,
            height=1080
        )
        
        assert meta.hash == "abc123def456"
        assert meta.size == 1024
        assert meta.width == 1920
        assert meta.height == 1080
    
    def test_metadata_equality_by_hash(self):
        """Test metadata equality is based on hash."""
        meta1 = ScreenshotMetadata("hash1", 1024, 1920, 1080)
        meta2 = ScreenshotMetadata("hash1", 2048, 1920, 1080)
        meta3 = ScreenshotMetadata("hash2", 1024, 1920, 1080)
        
        assert meta1 == meta2  # Same hash
        assert meta1 != meta3  # Different hash
    
    def test_metadata_not_equal_to_other_type(self):
        """Test metadata inequality with other types."""
        meta = ScreenshotMetadata("hash", 1024, 1920, 1080)
        
        assert meta != "hash"
        assert meta != 123
        assert meta != None


class TestScreenshotComparator:
    """Tests for ScreenshotComparator."""
    
    def test_comparator_initialization(self):
        """Test creating comparator."""
        comp = ScreenshotComparator()
        
        assert comp.last_screenshot is None
        assert comp.last_metadata is None
    
    def test_compute_hash(self):
        """Test hash computation."""
        screenshot1 = b"test_screenshot_1"
        screenshot2 = b"test_screenshot_2"
        
        hash1 = ScreenshotComparator.compute_hash(screenshot1)
        hash2 = ScreenshotComparator.compute_hash(screenshot2)
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 hex digest length
        assert hash1 != hash2  # Different screenshots have different hashes
    
    def test_compute_hash_idempotent(self):
        """Test hash computation is idempotent."""
        screenshot = b"test_screenshot"
        
        hash1 = ScreenshotComparator.compute_hash(screenshot)
        hash2 = ScreenshotComparator.compute_hash(screenshot)
        
        assert hash1 == hash2
    
    def test_get_metadata(self):
        """Test getting metadata."""
        screenshot = b"test"
        
        meta = ScreenshotComparator.get_metadata(screenshot)
        
        assert isinstance(meta, ScreenshotMetadata)
        assert len(meta.hash) == 64
        assert meta.size == len(screenshot)
    
    def test_is_changed_first_call(self):
        """Test change detection on first call."""
        comp = ScreenshotComparator()
        screenshot = b"test"
        
        changed = comp.is_changed(screenshot)
        
        assert changed is True  # First call is always changed
    
    def test_is_changed_same_screenshot(self):
        """Test change detection with same screenshot."""
        comp = ScreenshotComparator()
        screenshot = b"test_screenshot"
        
        comp.update(screenshot)
        changed = comp.is_changed(screenshot)
        
        assert changed is False
    
    def test_is_changed_different_screenshot(self):
        """Test change detection with different screenshot."""
        comp = ScreenshotComparator()
        screenshot1 = b"screenshot_1"
        screenshot2 = b"screenshot_2"
        
        comp.update(screenshot1)
        changed = comp.is_changed(screenshot2)
        
        assert changed is True
    
    def test_update_reference(self):
        """Test updating reference screenshot."""
        comp = ScreenshotComparator()
        screenshot = b"test"
        
        meta = comp.update(screenshot)
        
        assert comp.last_screenshot == screenshot
        assert comp.last_metadata == meta
        assert meta.hash == ScreenshotComparator.compute_hash(screenshot)
    
    def test_pixel_difference_same(self):
        """Test pixel difference for same image (mock)."""
        screenshot = b"same_data"
        
        # Note: Real test would need PIL
        diff = ScreenshotComparator.pixel_difference(screenshot, screenshot)
        
        # Should handle gracefully
        assert diff is None or isinstance(diff, float)
    
    def test_get_diff_regions(self):
        """Test getting diff regions."""
        screenshot1 = b"source"
        screenshot2 = b"modified"
        
        # Note: Real test would need PIL
        regions = ScreenshotComparator.get_diff_regions(screenshot1, screenshot2)
        
        assert isinstance(regions, list)


class TestScreenshotCache:
    """Tests for ScreenshotCache."""
    
    def test_cache_initialization(self):
        """Test cache initialization."""
        cache = ScreenshotCache()
        
        assert cache.max_cache == 10
        assert cache.cache == {}
        assert cache.order == []
    
    def test_cache_with_custom_size(self):
        """Test cache with custom max size."""
        cache = ScreenshotCache(max_cache=50)
        
        assert cache.max_cache == 50
    
    def test_add_screenshot(self):
        """Test adding screenshot to cache."""
        cache = ScreenshotCache()
        screenshot = b"test"
        
        hash_val = cache.add(screenshot)
        
        assert isinstance(hash_val, str)
        assert cache.get(hash_val) == screenshot
        assert len(cache.order) == 1
    
    def test_add_duplicate_screenshot(self):
        """Test adding duplicate screenshot."""
        cache = ScreenshotCache()
        screenshot = b"test"
        
        hash1 = cache.add(screenshot)
        hash2 = cache.add(screenshot)
        
        assert hash1 == hash2
        assert cache.size() == 1  # Only one unique screenshot
    
    def test_cache_different_screenshots(self):
        """Test caching different screenshots."""
        cache = ScreenshotCache()
        
        hash1 = cache.add(b"screenshot_1")
        hash2 = cache.add(b"screenshot_2")
        hash3 = cache.add(b"screenshot_3")
        
        assert len({hash1, hash2, hash3}) == 3  # All different
        assert cache.size() == 3
    
    def test_get_existing_screenshot(self):
        """Test retrieving cached screenshot."""
        cache = ScreenshotCache()
        screenshot = b"test_data"
        
        hash_val = cache.add(screenshot)
        result = cache.get(hash_val)
        
        assert result == screenshot
    
    def test_get_nonexistent_screenshot(self):
        """Test retrieving non-existent screenshot."""
        cache = ScreenshotCache()
        
        result = cache.get("nonexistent_hash")
        
        assert result is None
    
    def test_get_by_index(self):
        """Test retrieving screenshot by index."""
        cache = ScreenshotCache()
        screenshots = [b"img1", b"img2", b"img3"]
        
        for img in screenshots:
            cache.add(img)
        
        assert cache.get_by_index(0) == b"img1"
        assert cache.get_by_index(1) == b"img2"
        assert cache.get_by_index(2) == b"img3"
    
    def test_get_by_index_negative(self):
        """Test retrieving screenshot by negative index."""
        cache = ScreenshotCache()
        
        cache.add(b"img1")
        cache.add(b"img2")
        cache.add(b"img3")
        
        assert cache.get_by_index(-1) == b"img3"  # Last
        assert cache.get_by_index(-2) == b"img2"  # Second to last
    
    def test_get_by_index_out_of_range(self):
        """Test retrieving index out of range."""
        cache = ScreenshotCache()
        
        cache.add(b"img1")
        
        assert cache.get_by_index(5) is None
        assert cache.get_by_index(-5) is None
    
    def test_get_last(self):
        """Test getting last screenshot."""
        cache = ScreenshotCache()
        
        cache.add(b"img1")
        cache.add(b"img2")
        cache.add(b"img3")
        
        last = cache.get_last()
        
        assert last == b"img3"
    
    def test_get_last_empty(self):
        """Test getting last from empty cache."""
        cache = ScreenshotCache()
        
        last = cache.get_last()
        
        assert last is None
    
    def test_cache_size(self):
        """Test cache size reporting."""
        cache = ScreenshotCache()
        
        assert cache.size() == 0
        
        cache.add(b"img1")
        assert cache.size() == 1
        
        cache.add(b"img2")
        assert cache.size() == 2
    
    def test_cache_eviction(self):
        """Test cache eviction when exceeded."""
        cache = ScreenshotCache(max_cache=3)
        
        cache.add(b"img1")
        cache.add(b"img2")
        cache.add(b"img3")
        cache.add(b"img4")  # Should evict img1
        
        assert cache.size() == 3
        assert cache.get_by_index(0) == b"img2"  # img1 evicted
        assert cache.get_by_index(-1) == b"img4"  # Newest
    
    def test_cache_order_preserved(self):
        """Test cache maintains insertion order."""
        cache = ScreenshotCache()
        
        screenshots = [b"old", b"recent", b"newest"]
        for img in screenshots:
            cache.add(img)
        
        order = [cache.get_by_index(i) for i in range(cache.size())]
        
        assert order == screenshots
    
    def test_clear_cache(self):
        """Test clearing cache."""
        cache = ScreenshotCache()
        
        cache.add(b"img1")
        cache.add(b"img2")
        
        assert cache.size() == 2
        
        cache.clear()
        
        assert cache.size() == 0
        assert cache.get_last() is None


class TestScreenshotCacheEdgeCases:
    """Tests for edge cases."""
    
    def test_cache_with_large_max(self):
        """Test cache with very large max size."""
        cache = ScreenshotCache(max_cache=10000)
        
        for i in range(100):
            cache.add(f"img{i}".encode())
        
        assert cache.size() == 100
    
    def test_cache_with_size_one(self):
        """Test cache with max_cache=1."""
        cache = ScreenshotCache(max_cache=1)
        
        cache.add(b"img1")
        assert cache.size() == 1
        
        cache.add(b"img2")
        assert cache.size() == 1
        assert cache.get_last() == b"img2"
    
    def test_empty_screenshot(self):
        """Test caching empty screenshot."""
        cache = ScreenshotCache()
        
        hash_val = cache.add(b"")
        
        assert cache.get(hash_val) == b""
        assert cache.size() == 1
    
    def test_large_screenshot(self):
        """Test caching large screenshot."""
        cache = ScreenshotCache()
        large_data = b"x" * (10 * 1024 * 1024)  # 10MB
        
        hash_val = cache.add(large_data)
        
        assert cache.get(hash_val) == large_data
        assert cache.size() == 1
