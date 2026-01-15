"""Tests for billing form submission and verification flow."""
import unittest
from unittest.mock import MagicMock, patch

from src.personal_assistant.form_filler import FormDataRetriever
from src.personal_assistant.mock_tools import MockMemoryTools


class TestPaymentResultDetection(unittest.TestCase):
    """Test payment result detection from page content."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
    
    def test_detect_success_from_text(self):
        """Detect successful payment from page text."""
        page_text = "Payment successful! Your order has been confirmed. Order ID: 12345"
        result = self.retriever.detect_payment_result(page_text, "")
        
        self.assertEqual(result["status"], "success")
        self.assertGreater(result["confidence"], 0.0)
        self.assertIn("successful", result["message"].lower())
    
    def test_detect_failure_declined(self):
        """Detect declined card from page text."""
        page_text = "Card declined. Please try a different payment method."
        result = self.retriever.detect_payment_result(page_text, "")
        
        self.assertEqual(result["status"], "failed")
        self.assertIn("declined", result["reason"])
    
    def test_detect_failure_insufficient_funds(self):
        """Detect insufficient funds error."""
        page_text = "Error: Insufficient funds on this card. Please try another card."
        result = self.retriever.detect_payment_result(page_text, "")
        
        self.assertEqual(result["status"], "failed")
        self.assertIn("insufficient", result["reason"])
    
    def test_detect_failure_expired_card(self):
        """Detect expired card error."""
        page_text = "Error: Expired card. Please use a valid card."
        result = self.retriever.detect_payment_result(page_text, "")
        
        self.assertEqual(result["status"], "failed")
        self.assertIn("expired", result["reason"])
    
    def test_detect_unknown_when_ambiguous(self):
        """Return unknown when page content is ambiguous."""
        page_text = "Processing your request. Please wait."
        result = self.retriever.detect_payment_result(page_text, "")
        
        self.assertEqual(result["status"], "unknown")
    
    def test_html_classes_boost_confidence(self):
        """HTML class names should boost detection confidence."""
        page_text = "Order confirmed"
        page_html = '<div class="payment-success">Order confirmed</div>'
        result = self.retriever.detect_payment_result(page_text, page_html)
        
        self.assertEqual(result["status"], "success")
        self.assertGreater(result["confidence"], 0.3)


class TestPaymentMethodStorage(unittest.TestCase):
    """Test payment method storage with validity status."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
    
    def test_store_valid_payment_method(self):
        """Store a validated payment method."""
        uuid = self.retriever.store_payment_method(
            card_last_four="4242",
            props={"card_type": "visa", "name": "John Test"},
            is_valid=True
        )
        
        self.assertIsNotNone(uuid)
        # Check it was stored
        stored = self.memory.nodes.get(uuid)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.kind, "PaymentMethod")
        self.assertTrue(stored.props.get("is_valid"))
    
    def test_store_invalid_payment_method(self):
        """Store a rejected payment method with reason."""
        uuid = self.retriever.store_payment_method(
            card_last_four="0002",
            props={"card_type": "visa"},
            is_valid=False,
            failure_reason="declined"
        )
        
        self.assertIsNotNone(uuid)
        stored = self.memory.nodes.get(uuid)
        self.assertFalse(stored.props.get("is_valid"))
        self.assertEqual(stored.props.get("failure_reason"), "declined")


class TestPaymentPromptGeneration(unittest.TestCase):
    """Test prompt generation for billing data requests."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
    
    def test_generic_prompt(self):
        """Generate generic payment prompt."""
        prompt = self.retriever.build_payment_prompt()
        
        self.assertIn("Card Number", prompt)
        self.assertIn("Expiry", prompt)
        self.assertIn("CVV", prompt)
    
    def test_declined_card_prompt(self):
        """Generate prompt for declined card."""
        prompt = self.retriever.build_payment_prompt(failure_reason="declined")
        
        self.assertIn("declined", prompt.lower())
        self.assertIn("different card", prompt.lower())
    
    def test_insufficient_funds_prompt(self):
        """Generate prompt for insufficient funds."""
        prompt = self.retriever.build_payment_prompt(failure_reason="insufficient funds")
        
        self.assertIn("insufficient", prompt.lower())
    
    def test_expired_card_prompt(self):
        """Generate prompt for expired card."""
        prompt = self.retriever.build_payment_prompt(failure_reason="expired card")
        
        self.assertIn("expired", prompt.lower())


class TestGetValidPaymentMethods(unittest.TestCase):
    """Test retrieval of valid payment methods."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
    
    def test_get_valid_methods_only(self):
        """Only return payment methods marked as valid."""
        from src.personal_assistant.models import Node, Provenance
        from datetime import datetime, timezone
        
        prov = Provenance("test", datetime.now(timezone.utc).isoformat(), 1.0, "test")
        
        # Store a valid method
        valid_node = Node(
            kind="PaymentMethod",
            labels=["PaymentMethod"],
            props={"card_last_four": "4242", "is_valid": True}
        )
        self.memory.upsert(valid_node, prov)
        
        # Store an invalid method
        invalid_node = Node(
            kind="PaymentMethod",
            labels=["PaymentMethod"],
            props={"card_last_four": "0002", "is_valid": False}
        )
        self.memory.upsert(invalid_node, prov)
        
        # Get valid methods
        valid_methods = self.retriever.get_valid_payment_methods()
        
        # Should only contain the valid one
        valid_cards = [m.get("props", {}).get("card_last_four") for m in valid_methods]
        self.assertIn("4242", valid_cards)
        self.assertNotIn("0002", valid_cards)


if __name__ == "__main__":
    unittest.main()
