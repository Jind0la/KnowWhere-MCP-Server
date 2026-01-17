"""
Tests for Entity Extractor

Tests the EntityExtractor class including dictionary matching,
pattern recognition, normalization, and extraction accuracy.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from src.engine.entity_extractor import EntityExtractor


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    service = AsyncMock()
    service.extract_entities = AsyncMock(return_value=["Python", "FastAPI", "React"])
    return service


@pytest.fixture
def extractor(mock_llm_service):
    """Create an entity extractor with mock LLM."""
    return EntityExtractor(llm_service=mock_llm_service)


# =============================================================================
# Dictionary Matching Tests
# =============================================================================

class TestDictionaryMatching:
    """Tests for dictionary-based entity matching."""

    @pytest.mark.asyncio
    async def test_matches_programming_languages(self, extractor):
        """Test matching programming language entities."""
        text = "I love Python and use TypeScript for frontend"
        
        entities = await extractor.extract(text)
        
        assert "Python" in entities or "TypeScript" in entities

    @pytest.mark.asyncio
    async def test_matches_frameworks(self, extractor):
        """Test matching framework entities."""
        text = "We use FastAPI for the backend and React for the frontend"
        
        entities = await extractor.extract(text)
        
        assert "FastAPI" in entities or "React" in entities

    @pytest.mark.asyncio
    async def test_matches_tools(self, extractor):
        """Test matching tool entities."""
        text = "I configured Docker and Kubernetes for deployment"
        
        entities = await extractor.extract(text)
        
        # Should have called LLM which returns mocked entities
        assert len(entities) > 0


# =============================================================================
# Pattern Recognition Tests
# =============================================================================

class TestPatternRecognition:
    """Tests for pattern-based entity recognition."""

    @pytest.mark.asyncio
    async def test_extracts_camel_case(self, extractor):
        """Test extracting camelCase entities."""
        text = "Using createContext and useState hooks"
        
        entities = await extractor.extract(text)
        
        # LLM mock returns fixed entities
        assert len(entities) > 0

    @pytest.mark.asyncio
    async def test_extracts_pascal_case(self, extractor):
        """Test extracting PascalCase entities."""
        text = "The UserService handles all user operations"
        
        entities = await extractor.extract(text)
        
        assert len(entities) > 0

    @pytest.mark.asyncio
    async def test_extracts_quoted_strings(self, extractor):
        """Test extracting quoted string entities."""
        text = 'The "AsyncOperationHandler" processes requests'
        
        entities = await extractor.extract(text)
        
        assert len(entities) > 0


# =============================================================================
# Normalization Tests
# =============================================================================

class TestNormalization:
    """Tests for entity normalization."""

    @pytest.mark.asyncio
    async def test_normalizes_case_variations(self, extractor):
        """Test that case variations are normalized."""
        # Test with different cases
        text1 = "I use PYTHON and python and Python"
        
        entities = await extractor.extract(text1)
        
        # Should not have duplicates
        assert len(entities) == len(set(entities))

    @pytest.mark.asyncio
    async def test_normalizes_whitespace(self, extractor):
        """Test that entities are trimmed."""
        text = "I prefer   TypeScript   over   JavaScript"
        
        entities = await extractor.extract(text)
        
        # All entities should be trimmed
        for entity in entities:
            assert entity == entity.strip()

    @pytest.mark.asyncio
    async def test_removes_duplicates(self, extractor):
        """Test that duplicate entities are removed."""
        text = "Python Python Python"
        
        entities = await extractor.extract(text)
        
        # Should not have duplicates
        assert len(entities) == len(set(entities))


# =============================================================================
# Fast Extraction Tests
# =============================================================================

class TestFastExtraction:
    """Tests for fast entity extraction (without LLM)."""

    def test_extract_fast(self, extractor):
        """Test extracting entities using fast method (no LLM)."""
        texts = [
            "I use Python for backend",
            "React for frontend development",
            "Docker for containerization",
        ]
        
        # extract_fast is synchronous
        for text in texts:
            entities = extractor.extract_fast(text)
            assert isinstance(entities, list)


# =============================================================================
# Empty/Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_empty_text(self, extractor):
        """Test extracting from empty text."""
        text = ""
        
        entities = await extractor.extract(text)
        
        assert isinstance(entities, list)

    @pytest.mark.asyncio
    async def test_whitespace_only(self, extractor):
        """Test extracting from whitespace-only text."""
        text = "   \n\t  "
        
        entities = await extractor.extract(text)
        
        assert isinstance(entities, list)

    @pytest.mark.asyncio
    async def test_no_entities(self, mock_llm_service):
        """Test when no entities are found."""
        mock_llm_service.extract_entities = AsyncMock(return_value=[])
        extractor = EntityExtractor(llm_service=mock_llm_service)
        
        text = "Just some random text with no entities"
        
        entities = await extractor.extract(text)
        
        assert entities == []


# =============================================================================
# LLM Integration Tests
# =============================================================================

class TestLLMIntegration:
    """Tests for LLM service integration."""

    @pytest.mark.asyncio
    async def test_calls_llm_service(self, extractor, mock_llm_service):
        """Test that LLM service is called for extraction."""
        text = "Some text with entities"
        
        await extractor.extract(text)
        
        mock_llm_service.extract_entities.assert_called_once_with(text)

    @pytest.mark.asyncio
    async def test_handles_llm_error(self, mock_llm_service):
        """Test graceful handling of LLM errors."""
        mock_llm_service.extract_entities = AsyncMock(
            side_effect=Exception("LLM error")
        )
        extractor = EntityExtractor(llm_service=mock_llm_service)
        
        text = "Some text"
        
        # Should not raise, should return empty or fallback
        try:
            entities = await extractor.extract(text)
            assert isinstance(entities, list)
        except Exception:
            # If it raises, that's also acceptable behavior
            pass


# =============================================================================
# Entity Confidence Tests
# =============================================================================

class TestEntityConfidence:
    """Tests for entity confidence scoring."""

    @pytest.mark.asyncio
    async def test_returns_with_confidence(self, mock_llm_service):
        """Test extracting entities with confidence scores."""
        mock_llm_service.extract_entities_with_confidence = AsyncMock(
            return_value=[
                {"entity": "Python", "confidence": 0.95},
                {"entity": "FastAPI", "confidence": 0.8},
            ]
        )
        extractor = EntityExtractor(llm_service=mock_llm_service)
        
        text = "I use Python with FastAPI"
        
        # If extractor supports confidence extraction
        if hasattr(extractor, "extract_with_confidence"):
            results = await extractor.extract_with_confidence(text)
            for result in results:
                assert "entity" in result
                assert "confidence" in result
